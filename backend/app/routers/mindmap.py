import copy
import json
import re
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatHistory, MindMapVersion, StudyLog, User, WrongQuestion
from ..services.ai_service import build_text_tree, generate_mindmap, normalize_structured_chat, structured_to_mindmap
from ..services.behavior_modes import normalize_mode_key
from ..utils import err, ok

router = APIRouter(prefix="/mindmap", tags=["mindmap"])

SOURCE_CHAT = "chat"
SOURCE_WRONG = "wrong_question"
SOURCE_TOPIC = "topic"


class MindMapGenerateIn(BaseModel):
    source_type: Literal["chat", "wrong_question", "topic"]
    source_id: int | None = None
    topic: str | None = None
    mode_key: str = "general"


class MindMapTopicIn(BaseModel):
    topic: str
    mode_key: str = "general"


class MindMapSaveIn(BaseModel):
    id: int | None = None
    topic: str
    text_tree: str
    nodes: list[dict] = Field(default_factory=list)
    mindmap_id: str | None = None
    mode_key: str = "general"


class MindMapRollbackIn(BaseModel):
    version_id: int


class MindMapNodeEditIn(BaseModel):
    version_id: int
    operation_type: Literal["update_node", "add_child", "delete_node"]
    node_id: str
    parent_node_id: str | None = None
    label: str | None = None


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip()).strip("-")
    return value[:48] or "mindmap"


def _assign_node_ids(nodes: list[dict]) -> list[dict]:
    def walk(node: dict) -> dict:
        cloned = copy.deepcopy(node)
        cloned["id"] = cloned.get("id") or f"n_{uuid4().hex[:10]}"
        children = cloned.get("children") or []
        cloned["children"] = [walk(child) for child in children if isinstance(child, dict)]
        return cloned

    return [walk(node) for node in nodes if isinstance(node, dict)]


def _normalize_nodes(nodes: list[dict]) -> list[dict]:
    return _assign_node_ids(nodes)


def _serialize_nodes(nodes: list[dict]) -> str:
    return json.dumps(_normalize_nodes(nodes), ensure_ascii=False)


def _load_nodes(record: MindMapVersion) -> list[dict]:
    try:
        nodes = json.loads(record.nodes_json or "[]")
    except json.JSONDecodeError:
        nodes = []
    return _normalize_nodes(nodes)


def _serialize_version(record: MindMapVersion) -> dict:
    try:
        nodes = json.loads(record.nodes_json or "[]")
    except json.JSONDecodeError:
        nodes = []

    return {
        "id": record.id,
        "mindmap_id": record.mindmap_key,
        "version_no": record.version_no,
        "parent_version_id": record.parent_version_id,
        "source_type": record.source_type,
        "mode_key": getattr(record, "mode_key", "general"),
        "source_id": record.source_ref_id,
        "source_chat_id": record.source_chat_id,
        "source_wrong_question_id": record.source_wrong_question_id,
        "topic": record.topic,
        "text_tree": record.text_tree or "",
        "nodes": _normalize_nodes(nodes),
        "change_type": record.change_type,
        "change_summary": record.change_summary or "",
        "is_current": bool(record.is_current),
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _make_mindmap_key(source_type: str, source_id: int | None, topic: str) -> str:
    if source_type in {SOURCE_CHAT, SOURCE_WRONG} and source_id is not None:
        return f"{source_type}:{source_id}"
    return f"topic:{_slugify(topic)}"


def _latest_version(db: Session, user: User, mindmap_key: str) -> MindMapVersion | None:
    return (
        db.query(MindMapVersion)
        .filter(MindMapVersion.user_id == user.id, MindMapVersion.mindmap_key == mindmap_key)
        .order_by(MindMapVersion.version_no.desc(), MindMapVersion.id.desc())
        .first()
    )


def _latest_current_version(db: Session, user: User) -> MindMapVersion | None:
    return (
        db.query(MindMapVersion)
        .filter(MindMapVersion.user_id == user.id, MindMapVersion.is_current.is_(True))
        .order_by(MindMapVersion.updated_at.desc(), MindMapVersion.id.desc())
        .first()
    )


def _deactivate_versions(db: Session, user: User, mindmap_key: str) -> None:
    db.query(MindMapVersion).filter(MindMapVersion.user_id == user.id, MindMapVersion.mindmap_key == mindmap_key).update(
        {"is_current": False},
        synchronize_session=False,
    )


def _create_version(
    db: Session,
    user: User,
    *,
    mindmap_key: str,
    topic: str,
    nodes: list[dict],
    text_tree: str,
    source_type: str,
    mode_key: str,
    source_ref_id: int | None,
    source_chat_id: int | None,
    source_wrong_question_id: int | None,
    change_type: str,
    change_summary: str,
    source_snapshot_json: dict,
    parent_version: MindMapVersion | None = None,
) -> MindMapVersion:
    _deactivate_versions(db, user, mindmap_key)
    latest = parent_version or _latest_version(db, user, mindmap_key)
    version = MindMapVersion(
        user_id=user.id,
        mindmap_key=mindmap_key,
        version_no=(latest.version_no + 1 if latest else 1),
        parent_version_id=latest.id if latest else None,
        source_type=source_type,
        mode_key=normalize_mode_key(mode_key),
        source_ref_id=source_ref_id,
        source_chat_id=source_chat_id,
        source_wrong_question_id=source_wrong_question_id,
        topic=topic.strip() or "Mind Map",
        nodes_json=_serialize_nodes(nodes),
        text_tree=text_tree,
        source_snapshot_json=json.dumps(source_snapshot_json, ensure_ascii=False),
        change_type=change_type,
        change_summary=change_summary,
        is_current=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _extract_chat_structured(chat: ChatHistory) -> dict:
    try:
        raw = json.loads(chat.structured_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    return normalize_structured_chat(question=chat.question, subject=chat.subject, answer=chat.answer, structured=raw)


def _extract_wrong_structured(item: WrongQuestion) -> dict:
    bullets = [line.strip("-• \t") for line in (item.ai_analysis or "").splitlines() if line.strip()]
    return {
        "subject": item.subject or "Wrong Question",
        "topic": item.subject or "Wrong Question",
        "conclusion": item.question_text[:120] or "Wrong question review",
        "explanation": item.ai_analysis or "Review the wrong question and extract the weak point.",
        "example": {
            "question": item.question_text,
            "answer": "Refer to the analysis for the correct steps.",
            "analysis": item.ai_analysis or "",
        },
        "pitfalls": bullets[:4] or ["Review the root cause of the mistake."],
        "extensions": [item.subject or "wrong question review"],
        "knowledge_tags": [item.subject or "wrong question", "review"],
        "version": "v1",
    }


def _build_version_from_source(db: Session, user: User, payload: MindMapGenerateIn) -> MindMapVersion:
    source_snapshot: dict[str, object]
    source_type = payload.source_type
    topic = payload.topic or "Mind Map"
    source_ref_id = payload.source_id
    source_chat_id = None
    source_wrong_question_id = None
    mode_key = normalize_mode_key(payload.mode_key)
    structured: dict

    if source_type == SOURCE_CHAT:
        chat = db.query(ChatHistory).filter(ChatHistory.id == payload.source_id, ChatHistory.user_id == user.id).first()
        if not chat:
            raise ValueError("chat source not found")
        structured = _extract_chat_structured(chat)
        topic = payload.topic or structured.get("topic") or chat.subject or "Mind Map"
        source_ref_id = chat.id
        source_chat_id = chat.id
        mode_key = normalize_mode_key(getattr(chat, "mode_key", mode_key))
        source_snapshot = {
            "source_type": SOURCE_CHAT,
            "chat_id": chat.id,
            "question": chat.question,
            "answer": chat.answer,
            "structured": structured,
        }
    elif source_type == SOURCE_WRONG:
        item = db.query(WrongQuestion).filter(WrongQuestion.id == payload.source_id, WrongQuestion.user_id == user.id).first()
        if not item:
            raise ValueError("wrong question source not found")
        structured = _extract_wrong_structured(item)
        topic = payload.topic or structured.get("topic") or item.subject or "Mind Map"
        source_ref_id = item.id
        source_wrong_question_id = item.id
        mode_key = normalize_mode_key(getattr(item, "mode_key", mode_key))
        source_snapshot = {
            "source_type": SOURCE_WRONG,
            "wrong_question_id": item.id,
            "question_text": item.question_text,
            "analysis": item.ai_analysis,
            "structured": structured,
        }
    else:
        structured = {
            "topic": topic,
            "conclusion": topic,
            "explanation": topic,
            "example": {"question": topic, "answer": "", "analysis": ""},
            "pitfalls": [],
            "extensions": [],
            "knowledge_tags": [topic],
        }
        source_snapshot = {"source_type": SOURCE_TOPIC, "topic": topic}

    tree = structured_to_mindmap(structured)
    nodes = _normalize_nodes(tree.get("nodes") or [])
    text_tree = build_text_tree({"topic": tree.get("topic") or topic, "nodes": nodes})
    mindmap_key = _make_mindmap_key(source_type, source_ref_id, topic)
    latest = _latest_version(db, user, mindmap_key)
    if latest:
        return _create_version(
            db,
            user,
            mindmap_key=mindmap_key,
            topic=topic,
            nodes=nodes,
            text_tree=text_tree,
            source_type=source_type,
            mode_key=mode_key,
            source_ref_id=source_ref_id,
            source_chat_id=source_chat_id,
            source_wrong_question_id=source_wrong_question_id,
            change_type="generate",
            change_summary=f"Generate from {source_type}",
            source_snapshot_json=source_snapshot,
            parent_version=latest,
        )

    return _create_version(
        db,
        user,
        mindmap_key=mindmap_key,
        topic=topic,
        nodes=nodes,
        text_tree=text_tree,
        source_type=source_type,
        mode_key=mode_key,
        source_ref_id=source_ref_id,
        source_chat_id=source_chat_id,
        source_wrong_question_id=source_wrong_question_id,
        change_type="generate",
        change_summary=f"Generate from {source_type}",
        source_snapshot_json=source_snapshot,
    )


def _apply_to_nodes(nodes: list[dict], target_id: str, operation: str, label: str | None, parent_node_id: str | None) -> bool:
    for index, node in enumerate(nodes):
        if node.get("id") == target_id:
            if operation == "update_node":
                if label is not None:
                    node["label"] = label
                return True
            if operation == "delete_node":
                del nodes[index]
                return True
        children = node.get("children") or []
        if _apply_to_nodes(children, target_id, operation, label, parent_node_id):
            node["children"] = children
            return True
    return False


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    for node in nodes:
        if node.get("id") == node_id:
            return node
        found = _find_node(node.get("children") or [], node_id)
        if found:
            return found
    return None


def _edit_nodes(nodes: list[dict], payload: MindMapNodeEditIn) -> list[dict]:
    cloned = _normalize_nodes(nodes)
    if payload.operation_type == "update_node":
        updated = _apply_to_nodes(cloned, payload.node_id, "update_node", payload.label, payload.parent_node_id)
        if not updated:
            raise ValueError("node not found")
        return cloned

    if payload.operation_type == "delete_node":
        if _apply_to_nodes(cloned, payload.node_id, "delete_node", None, payload.parent_node_id):
            return cloned
        raise ValueError("node not found")

    new_node = {"id": f"n_{uuid4().hex[:10]}", "label": payload.label or "New Node", "children": []}
    if payload.parent_node_id:
        parent = _find_node(cloned, payload.parent_node_id)
        if not parent:
            raise ValueError("parent node not found")
        parent.setdefault("children", []).append(new_node)
        return cloned

    cloned.append(new_node)
    return cloned


@router.get("/latest")
def latest_mindmap(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = _latest_current_version(db, user)
    return ok(_serialize_version(record) if record else None)


@router.post("/generate")
def generate_from_source(payload: MindMapGenerateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        version = _build_version_from_source(db, user, payload)
    except ValueError as exc:
        return err(1002, str(exc))

    db.add(StudyLog(user_id=user.id, subject=version.topic[:50] or "Mind Map", duration=2))
    db.commit()
    return ok(_serialize_version(version), "generated")


@router.post("")
async def create_mindmap(payload: MindMapTopicIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    topic = payload.topic
    if not topic:
        return err(1002, "topic is required")
    result = await generate_mindmap(topic, payload.mode_key)
    normalized = _normalize_nodes(result.get("nodes") or [])
    text_tree = build_text_tree({"topic": result.get("topic") or topic, "nodes": normalized})
    version = _create_version(
        db,
        user,
        mindmap_key=_make_mindmap_key(SOURCE_TOPIC, None, topic),
        topic=result.get("topic") or topic,
        nodes=normalized,
        text_tree=text_tree,
        source_type=SOURCE_TOPIC,
        mode_key=normalize_mode_key(payload.mode_key),
        source_ref_id=None,
        source_chat_id=None,
        source_wrong_question_id=None,
        change_type="generate",
        change_summary="Generate from topic",
        source_snapshot_json={"source_type": SOURCE_TOPIC, "topic": topic, "result": result},
    )
    db.add(StudyLog(user_id=user.id, subject=topic[:50] or "Mind Map", duration=2))
    db.commit()
    return ok(_serialize_version(version))


@router.put("/save")
def save_mindmap(payload: MindMapSaveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    topic = payload.topic.strip() or "Mind Map"
    nodes = _normalize_nodes(payload.nodes or [])
    text_tree = payload.text_tree or build_text_tree({"topic": topic, "nodes": nodes})
    mindmap_key = payload.mindmap_id or _make_mindmap_key(SOURCE_TOPIC, payload.id, topic)
    parent = _latest_version(db, user, mindmap_key)
    version = _create_version(
        db,
        user,
        mindmap_key=mindmap_key,
        topic=topic,
        nodes=nodes,
        text_tree=text_tree,
        source_type=SOURCE_TOPIC,
        mode_key=normalize_mode_key(payload.mode_key),
        source_ref_id=payload.id,
        source_chat_id=None,
        source_wrong_question_id=None,
        change_type="edit",
        change_summary="Manual save",
        source_snapshot_json={"source_type": SOURCE_TOPIC, "topic": topic},
        parent_version=parent,
    )
    return ok(_serialize_version(version), "saved")


@router.get("/{mindmap_id}/versions")
def list_versions(mindmap_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = (
        db.query(MindMapVersion)
        .filter(MindMapVersion.user_id == user.id, MindMapVersion.mindmap_key == mindmap_id)
        .order_by(MindMapVersion.version_no.desc(), MindMapVersion.id.desc())
        .all()
    )
    return ok([_serialize_version(item) for item in items])


@router.post("/{mindmap_id}/rollback")
def rollback_version(
    mindmap_id: str,
    payload: MindMapRollbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = (
        db.query(MindMapVersion)
        .filter(MindMapVersion.id == payload.version_id, MindMapVersion.user_id == user.id, MindMapVersion.mindmap_key == mindmap_id)
        .first()
    )
    if not target:
        return err(1002, "version not found")

    version = _create_version(
        db,
        user,
        mindmap_key=mindmap_id,
        topic=target.topic,
        nodes=_load_nodes(target),
        text_tree=target.text_tree,
        source_type=target.source_type,
        mode_key=getattr(target, "mode_key", "general"),
        source_ref_id=target.source_ref_id,
        source_chat_id=target.source_chat_id,
        source_wrong_question_id=target.source_wrong_question_id,
        change_type="rollback",
        change_summary=f"Rollback to version {target.version_no}",
        source_snapshot_json=json.loads(target.source_snapshot_json or "{}"),
        parent_version=target,
    )
    return ok(_serialize_version(version), "rolled back")


@router.post("/{mindmap_id}/nodes/edit")
def edit_nodes(
    mindmap_id: str,
    payload: MindMapNodeEditIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current = (
        db.query(MindMapVersion)
        .filter(MindMapVersion.id == payload.version_id, MindMapVersion.user_id == user.id, MindMapVersion.mindmap_key == mindmap_id)
        .first()
    )
    if not current:
        return err(1002, "version not found")

    nodes = _load_nodes(current)
    try:
        edited_nodes = _edit_nodes(nodes, payload)
    except ValueError as exc:
        return err(1002, str(exc))

    text_tree = build_text_tree({"topic": current.topic, "nodes": edited_nodes})
    version = _create_version(
        db,
        user,
        mindmap_key=mindmap_id,
        topic=current.topic,
        nodes=edited_nodes,
        text_tree=text_tree,
        source_type=current.source_type,
        mode_key=getattr(current, "mode_key", "general"),
        source_ref_id=current.source_ref_id,
        source_chat_id=current.source_chat_id,
        source_wrong_question_id=current.source_wrong_question_id,
        change_type="edit",
        change_summary=f"Node {payload.operation_type}",
        source_snapshot_json=json.loads(current.source_snapshot_json or "{}"),
        parent_version=current,
    )
    return ok(_serialize_version(version), "updated")
