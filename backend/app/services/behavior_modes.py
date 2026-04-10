from __future__ import annotations

from copy import deepcopy

DEFAULT_MODE_KEY = "general"

MODE_REGISTRY: dict[str, dict] = {
    "general": {
        "mode_key": "general",
        "mode_name": "通用模式",
        "mode_type": "general",
        "description": "适合综合性、跨学科或暂时还没明确范围的问题。",
        "icon": "G",
        "color": "amber",
        "enabled": True,
        "sort_order": 0,
        "chat": {
            "system_prompt": (
                "你是一名学习助手。先给出直接结论，再解释原因，最后补充例子、易错点和下一步建议。"
                "如果问题跨多个学科，优先提供可迁移的分析框架。"
            ),
            "quiz_prompt": "围绕用户给定的知识点生成高质量练习题，覆盖基础理解和实际应用。",
            "mindmap_prompt": "生成结构清晰的思维导图，覆盖主题、核心概念、关键分支、例子和易错点。",
            "wrong_prompt": "分析错题时突出知识点、出错原因、正确思路和复习建议。",
        },
    },
    "computer": {
        "mode_key": "computer",
        "mode_name": "计算机模式",
        "mode_type": "subject",
        "description": "偏代码、算法、调试、工程实践和实现细节。",
        "icon": "C",
        "color": "blue",
        "enabled": True,
        "sort_order": 10,
        "chat": {
            "system_prompt": (
                "你是一名计算机学习助手。优先给出实现思路、边界条件、调试方法和可执行示例。"
                "术语要准确，步骤要清楚。"
            ),
            "quiz_prompt": "围绕计算机知识点生成题目，优先考查代码理解、算法分析、运行结果和边界条件。",
            "mindmap_prompt": "生成适合计算机学习的思维导图，涵盖概念、原理、示例、常见错误和最佳实践。",
            "wrong_prompt": "从概念理解、代码细节、边界条件和实现思路几个角度分析错题。",
        },
    },
    "english": {
        "mode_key": "english",
        "mode_name": "英语模式",
        "mode_type": "subject",
        "description": "偏翻译、语法、词汇、表达和纠错。",
        "icon": "E",
        "color": "green",
        "enabled": True,
        "sort_order": 20,
        "chat": {
            "system_prompt": (
                "你是一名英语学习助手。先帮助用户理解原文，再解释语法点，最后给出自然表达和例句。"
                "如果用户提供句子，要指出常见搭配和易错点。"
            ),
            "quiz_prompt": "围绕英语知识点生成题目，优先考查翻译、语法填空、词汇辨析、改写和完形。",
            "mindmap_prompt": "生成适合英语学习的思维导图，涵盖词汇、语法、句型、翻译技巧和易错点。",
            "wrong_prompt": "从语法、词义、搭配、时态、语序和语境几个角度分析错题。",
        },
    },
    "math": {
        "mode_key": "math",
        "mode_name": "数学模式",
        "mode_type": "subject",
        "description": "偏推导、公式、证明、步骤和例题。",
        "icon": "M",
        "color": "red",
        "enabled": True,
        "sort_order": 30,
        "chat": {
            "system_prompt": "你是一名数学学习助手。不要跳步，尽量完整写出关键推导链路、适用条件和结论验证。",
            "quiz_prompt": "围绕数学知识点生成题目，优先考查计算、证明、应用题和步骤推导。",
            "mindmap_prompt": "生成适合数学学习的思维导图，涵盖定理或公式、适用条件、推导过程、典型例题和易错点。",
            "wrong_prompt": "从公式理解、条件判断、推导过程、运算细节和结论验证几个角度分析错题。",
        },
    },
    "encourage": {
        "mode_key": "encourage",
        "mode_name": "鼓励模式",
        "mode_type": "emotion",
        "description": "适合疲惫、压力大或需要陪伴式鼓励时使用。",
        "icon": "H",
        "color": "pink",
        "enabled": True,
        "sort_order": 40,
        "chat": {
            "system_prompt": (
                "你是一名温和、稳定的学习陪伴助手。先安抚情绪，再给出一个最容易执行的下一步。"
                "避免制造压力，把任务拆成很小的行动。回答尽量自然对话化，不要强行组织成结论、例题或知识点清单。"
            ),
            "quiz_prompt": "用轻量、不施压的方式带用户做小步练习。",
            "mindmap_prompt": "如果需要生成思维导图，保持结构简洁、轻量、清楚。",
            "wrong_prompt": "用温和的方式帮助用户看待错误，重点给出最容易执行的修正建议。",
        },
    },
}


def normalize_mode_key(mode_key: str | None) -> str:
    key = (mode_key or DEFAULT_MODE_KEY).strip().lower()
    return key if key in MODE_REGISTRY else DEFAULT_MODE_KEY


def get_mode_profile(mode_key: str | None) -> dict:
    return deepcopy(MODE_REGISTRY[normalize_mode_key(mode_key)])


def list_mode_profiles() -> list[dict]:
    items = [deepcopy(item) for item in MODE_REGISTRY.values() if item.get("enabled", True)]
    items.sort(key=lambda item: item.get("sort_order", 999))
    return items


def build_chat_system_prompt(mode_key: str | None, subject: str) -> str:
    profile = get_mode_profile(mode_key)
    return f"{profile['chat']['system_prompt']} 当前学科：{subject or '通用'}。"


def build_quiz_prompt(mode_key: str | None, subject: str, topic: str, count: int) -> str:
    profile = get_mode_profile(mode_key)
    return (
        f"{profile['chat']['quiz_prompt']}\n"
        f"学科：{subject or '通用'}\n"
        f"知识点：{topic}\n"
        f"题目数量：{count}\n"
        "只返回 JSON 数组，数组中每一项都包含 question、options、answer、analysis。"
    )


def build_mindmap_prompt(mode_key: str | None, topic: str) -> str:
    profile = get_mode_profile(mode_key)
    return (
        f"{profile['chat']['mindmap_prompt']}\n"
        f"主题：{topic}\n"
        "只返回 JSON 对象，至少包含 topic 和 nodes，nodes 必须是树状结构数组。"
    )


def build_wrong_analysis_prompt(mode_key: str | None, subject: str, question_text: str) -> str:
    profile = get_mode_profile(mode_key)
    return (
        f"{profile['chat']['wrong_prompt']}\n"
        "请按以下结构输出：\n"
        "1. 考查知识点\n"
        "2. 常见出错原因\n"
        "3. 正确解题步骤\n"
        "4. 下一次复习建议\n\n"
        f"学科：{subject or '通用'}\n"
        f"题目：{question_text}"
    )
