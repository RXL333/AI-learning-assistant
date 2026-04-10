from __future__ import annotations

import json
import logging
import random
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import settings
from .behavior_modes import build_chat_system_prompt, build_mindmap_prompt, build_quiz_prompt, build_wrong_analysis_prompt, get_mode_profile

logger = logging.getLogger(__name__)

RELATED_TOPICS = ["核心概念回顾", "高频考点", "典型题型训练"]
STRUCTURED_VERSION = "v2"
HTTP_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)


def _mode_name(mode_key: str | None) -> str:
    return get_mode_profile(mode_key).get("mode_name", "通用模式")


def _subject_text(subject: str | None) -> str:
    return (subject or "").strip() or "通用"


def _question_headline(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return "这个问题"
    return value.splitlines()[0][:120]


def _default_followups(topic: str) -> list[str]:
    topic = (topic or "").strip() or "这个知识点"
    return [
        f"{topic} 的核心判断条件是什么？",
        f"如果把题目条件改动一点，结论会怎么变化？",
        f"{topic} 最容易和哪类问题混淆？",
    ]


def _chat_error_message(exc: Exception) -> str:
    logger.warning("chat completion failed: %s", exc)
    return "AI 服务暂时不可用，请稍后重试。"


def _fallback_chat_answer(question: str, subject: str, mode_key: str) -> str:
    mode_name = _mode_name(mode_key)
    subject_text = _subject_text(subject)
    headline = _question_headline(question)
    return (
        "下面先给你一个离线兜底答案。\n\n"
        f"当前模式：{mode_name}\n"
        f"当前学科：{subject_text}\n\n"
        f"问题核心：{headline}\n\n"
        "建议先按这三个步骤处理：\n"
        "1. 先确认题目条件和目标是什么。\n"
        "2. 把问题拆成几个小步骤逐个处理。\n"
        "3. 最后回到结论，检查有没有遗漏边界条件。\n\n"
        "如果你愿意，我可以继续把它展开成更细的解析、例子和易错点。"
    )


def _fallback_wrong_analysis(subject: str, question_text: str) -> str:
    subject_text = _subject_text(subject)
    headline = _question_headline(question_text)
    return (
        f"1. 考查知识点\n围绕 {subject_text} 的核心概念和题目条件。\n\n"
        "2. 常见错误原因\n审题不清、概念混淆、步骤遗漏、边界条件忽略。\n\n"
        "3. 正确解题思路\n先定位知识点，再逐步推导，最后检查结果是否满足题意。\n\n"
        "4. 下次复习建议\n把这类题再做 2 到 3 道，并整理成错因卡片。\n\n"
        f"题干摘要：{headline}"
    )


def _fallback_quiz(subject: str, topic: str, count: int) -> list[dict[str, Any]]:
    options = ["A", "B", "C", "D"]
    quizzes = []
    for i in range(max(1, count)):
        answer = random.choice(options)
        quizzes.append(
            {
                "question": f"[{_subject_text(subject)}] {topic} 练习题 {i + 1}：以下说法正确的是？",
                "options": [f"{opt}. 选项 {opt}" for opt in options],
                "answer": answer,
                "analysis": f"本题的正确答案是 {answer}，建议结合题目条件逐步排除干扰项。",
            }
        )
    return quizzes[:count]


def _fallback_mindmap(topic: str, subject: str | None = None) -> dict[str, Any]:
    title = (topic or "").strip() or _subject_text(subject) or "思维导图"
    nodes = [
        {
            "label": title,
            "children": [
                {
                    "label": "核心概念",
                    "children": [
                        {"label": "定义", "children": []},
                        {"label": "关键术语", "children": []},
                    ],
                },
                {
                    "label": "重点内容",
                    "children": [
                        {"label": "常考点", "children": []},
                        {"label": "易错点", "children": []},
                    ],
                },
                {
                    "label": "学习方法",
                    "children": [
                        {"label": "先理解后练习", "children": []},
                        {"label": "结合案例复盘", "children": []},
                    ],
                },
            ],
        }
    ]
    result = {"topic": title, "nodes": nodes}
    result["text_tree"] = build_text_tree(result)
    return result


def _normalize_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _extract_json_blob(text: str) -> Any | None:
    raw = (text or "").strip()
    if not raw:
        return None

    candidates: list[str] = [raw]
    object_start = raw.find("{")
    object_end = raw.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(raw[object_start : object_end + 1])

    array_start = raw.find("[")
    array_end = raw.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidates.append(raw[array_start : array_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _clean_content(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def normalize_structured_chat(
    *,
    question: str,
    subject: str,
    answer: str,
    structured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = structured or {}
    subject_text = _subject_text(subject)
    headline = _question_headline(question)
    answer_text = (answer or "").strip() or headline

    example = base.get("example") if isinstance(base.get("example"), dict) else {}
    topic = str(base.get("topic", "")).strip() or headline[:40] or subject_text

    return {
        "conclusion": str(base.get("conclusion", "")).strip() or answer_text.splitlines()[0][:200],
        "explanation": str(base.get("explanation", "")).strip() or answer_text,
        "example": {
            "question": str(example.get("question", "")).strip() or question,
            "answer": str(example.get("answer", "")).strip() or "请根据解析自行补全答案。",
            "analysis": str(example.get("analysis", "")).strip() or answer_text[:500],
        },
        "pitfalls": (_normalize_list(base.get("pitfalls")) or ["审题不清", "概念混淆", "步骤遗漏"])[:6],
        "extensions": (_normalize_list(base.get("extensions")) or RELATED_TOPICS)[:6],
        "knowledge_tags": (_normalize_list(base.get("knowledge_tags")) or [subject_text])[:8],
        "follow_ups": (_normalize_list(base.get("follow_ups")) or _default_followups(topic))[:3],
        "subject": subject_text,
        "topic": topic,
        "version": STRUCTURED_VERSION,
    }


def build_text_tree(data: dict[str, Any]) -> str:
    nodes = data.get("nodes") or []
    if not nodes:
        return str(data.get("topic", "思维导图"))

    lines: list[str] = []

    def walk(node: dict[str, Any], depth: int = 0) -> None:
        label = str(node.get("label", "未命名节点")).strip() or "未命名节点"
        indent = "  " * depth
        prefix = "" if depth == 0 else "-> "
        lines.append(f"{indent}{prefix}{label}")
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child, depth + 1)

    for node in nodes:
        if isinstance(node, dict):
            walk(node)
    return "\n".join(lines)


def structured_to_mindmap(structured: dict[str, Any]) -> dict[str, Any]:
    topic = str(structured.get("topic", "")).strip() or str(structured.get("subject", "思维导图"))
    pitfalls = _normalize_list(structured.get("pitfalls")) or ["审题不清", "概念混淆"]
    extensions = _normalize_list(structured.get("extensions")) or RELATED_TOPICS
    tags = _normalize_list(structured.get("knowledge_tags")) or [topic]

    nodes = [
        {
            "label": topic,
            "children": [
                {"label": "结论", "children": [{"label": str(structured.get("conclusion", "")).strip() or "暂无结论", "children": []}]},
                {"label": "解释", "children": [{"label": str(structured.get("explanation", "")).strip()[:120] or "暂无解释", "children": []}]},
                {"label": "例题", "children": [{"label": str((structured.get("example") or {}).get("question", "")).strip() or "暂无例题", "children": []}]},
                {"label": "易错点", "children": [{"label": item, "children": []} for item in pitfalls[:6]]},
                {"label": "延伸知识", "children": [{"label": item, "children": []} for item in extensions[:6]]},
                {"label": "知识标签", "children": [{"label": item, "children": []} for item in tags[:8]]},
            ],
        }
    ]
    result = {"topic": topic, "nodes": nodes}
    result["text_tree"] = build_text_tree(result)
    return result


def _build_messages(mode_key: str, subject: str, question: str) -> list[dict[str, str]]:
    system_prompt = build_chat_system_prompt(mode_key, subject)
    return [
        {
            "role": "system",
            "content": (
                f"{system_prompt}\n"
                "请用中文回答，先给结论，再给简要解释，最后给下一步建议。"
            ),
        },
        {
            "role": "user",
            "content": f"学科：{subject}\n问题：{question}",
        },
    ]


def _build_json_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                f"{system_prompt}\n"
                "严格只输出 JSON，不要输出额外解释、代码块或 Markdown。"
            ),
        },
        {"role": "user", "content": user_prompt},
    ]


async def _chat_completion(messages: list[dict[str, str]], *, temperature: float = 0.2) -> dict[str, Any]:
    base_url = (settings.openai_base_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not configured")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def _stream_completion(messages: list[dict[str, str]], *, temperature: float = 0.2) -> AsyncIterator[str]:
    base_url = (settings.openai_base_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not configured")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_text = line[5:].strip()
                if data_text == "[DONE]":
                    break
                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or ""
                if content:
                    yield content


def _choice_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if content is None:
        content = first.get("text", "")
    return _clean_content(str(content or ""))


def _normalize_quiz_items(value: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(value, dict):
        value = value.get("questions") or value.get("items") or value.get("data") or []
    if not isinstance(value, list):
        return items

    for item in value:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        if not isinstance(options, list):
            options = []
        items.append(
            {
                "question": str(item.get("question", "")).strip(),
                "options": [str(opt).strip() for opt in options if str(opt).strip()],
                "answer": str(item.get("answer", "")).strip(),
                "analysis": str(item.get("analysis", "")).strip(),
            }
        )
    return [item for item in items if item["question"]]


def _normalize_mindmap_payload(value: Any, topic: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    title = str(value.get("topic", "")).strip() or topic
    nodes = value.get("nodes")
    if not isinstance(nodes, list):
        nodes = []

    result = {
        "topic": title,
        "nodes": nodes,
    }
    result["text_tree"] = build_text_tree(result)
    if not result["nodes"]:
        return None
    return result


async def ask_ai(question: str, subject: str, mode_key: str = "general") -> tuple[str, dict[str, Any], str, list[str], bool]:
    try:
        data = await _chat_completion(_build_messages(mode_key, subject, question), temperature=0.25)
        answer = _choice_content(data)
        if not answer:
            raise ValueError("empty model response")

        structured_payload = _extract_json_blob(answer)
        if isinstance(structured_payload, dict):
            answer_text = str(structured_payload.get("answer") or structured_payload.get("content") or answer).strip()
            structured = normalize_structured_chat(
                question=question,
                subject=subject,
                answer=answer_text,
                structured=structured_payload,
            )
            related_topics = _normalize_list(structured_payload.get("related_topics")) or structured.get("extensions", [])
            return answer_text, structured, "ai", related_topics[:6], False

        structured = normalize_structured_chat(question=question, subject=subject, answer=answer)
        return answer, structured, "ai", structured.get("extensions", [])[:6], False
    except Exception as exc:
        return _chat_error_message(exc), {}, "error", [], True


async def stream_ai(question: str, subject: str, mode_key: str = "general") -> AsyncIterator[dict[str, Any]]:
    try:
        answer_parts: list[str] = []
        async for chunk in _stream_completion(_build_messages(mode_key, subject, question), temperature=0.25):
            answer_parts.append(chunk)
            yield {"type": "delta", "content": chunk}

        answer = "".join(answer_parts).strip()
        if not answer:
            raise ValueError("empty model response")

        structured = normalize_structured_chat(question=question, subject=subject, answer=answer)
        yield {
            "type": "done",
            "answer": answer,
            "structured": structured,
            "structured_quality": "ai",
            "related_topics": structured.get("extensions", [])[:6],
            "is_error": False,
        }
    except Exception as exc:
        yield {"type": "error", "message": _chat_error_message(exc), "is_error": True}


async def analyze_wrong_question(subject: str, question_text: str, mode_key: str = "general") -> str:
    try:
        messages = _build_json_messages(
            build_wrong_analysis_prompt(mode_key, subject, question_text),
            (
                f"学科：{subject}\n"
                f"题目：{question_text}\n"
                "输出一段分点分析，包含：考查知识点、常见错误原因、正确解题思路、下次复习建议。"
            ),
        )
        data = await _chat_completion(messages, temperature=0.25)
        content = _choice_content(data)
        if content:
            return content
    except Exception as exc:
        logger.warning("wrong analysis failed, fallback used: %s", exc)
    return _fallback_wrong_analysis(subject, question_text)


async def generate_quiz(subject: str, topic: str, count: int, mode_key: str = "general") -> list[dict[str, Any]]:
    try:
        messages = _build_json_messages(
            build_quiz_prompt(mode_key, subject, topic, count),
            (
                f"学科：{subject}\n"
                f"知识点：{topic}\n"
                f"题目数量：{count}\n"
                "返回 JSON 数组，每项都包含 question、options、answer、analysis。"
            ),
        )
        data = await _chat_completion(messages, temperature=0.45)
        content = _choice_content(data)
        payload = _extract_json_blob(content)
        quizzes = _normalize_quiz_items(payload)
        if quizzes:
            return quizzes[:count]
    except Exception as exc:
        logger.warning("quiz generation failed, fallback used: %s", exc)
    return _fallback_quiz(subject, topic, count)


async def generate_mindmap(topic: str, mode_key: str = "general") -> dict[str, Any]:
    try:
        messages = _build_json_messages(
            build_mindmap_prompt(mode_key, topic),
            (
                f"主题：{topic}\n"
                "返回 JSON 对象，至少包含 topic 和 nodes；nodes 必须是树状结构数组，每个节点至少包含 label 和 children。"
            ),
        )
        data = await _chat_completion(messages, temperature=0.3)
        content = _choice_content(data)
        payload = _extract_json_blob(content)
        mindmap = _normalize_mindmap_payload(payload, topic)
        if mindmap:
            return mindmap

        if isinstance(payload, dict):
            structured = {
                "topic": str(payload.get("topic", "")).strip() or topic,
                "conclusion": str(payload.get("conclusion", "")).strip() or topic,
                "explanation": str(payload.get("explanation", "")).strip() or topic,
                "example": payload.get("example") or {"question": topic, "answer": "", "analysis": ""},
                "pitfalls": payload.get("pitfalls") or [],
                "extensions": payload.get("extensions") or [],
                "knowledge_tags": payload.get("knowledge_tags") or [topic],
            }
            return structured_to_mindmap(structured)
    except Exception as exc:
        logger.warning("mindmap generation failed, fallback used: %s", exc)
    return _fallback_mindmap(topic)
