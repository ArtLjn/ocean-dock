"""Session 数据读取层"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import jsonlines

from ocean_dock.models import MessageType, Session, SessionKind, SessionMessage
from ocean_dock.utils import (
    PROJECTS_DIR,
    SESSIONS_DIR,
    decode_project_path,
    extract_text_from_message,
    parse_timestamp,
)


def _parse_iso_to_datetime(ts: str) -> datetime | None:
    """将 ISO 时间字符串解析为 datetime。"""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except (ValueError, AttributeError, TypeError):
        return None


def load_session_from_jsonl(jsonl_path: Path, project_path: str = "") -> Session | None:
    """从 JSONL 文件快速扫描 session 元数据（不加载完整消息列表）。"""
    try:
        session_id = jsonl_path.stem
        started_at = None
        last_at = None
        cwd = project_path
        entrypoint = ""
        first_user_msg = ""
        user_count = 0
        assistant_count = 0

        with open(jsonl_path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type", "")

                if obj.get("timestamp"):
                    ts = _parse_iso_to_datetime(obj["timestamp"])
                    if ts:
                        if started_at is None:
                            started_at = ts
                        last_at = ts

                if msg_type == "user":
                    user_count += 1
                    # 优先使用 JSONL 中的真实路径，decode_project_path 对 _ 和非 ASCII 字符解码有歧义
                    jsonl_cwd = obj.get("cwd", "")
                    if jsonl_cwd:
                        cwd = jsonl_cwd
                    if not entrypoint:
                        entrypoint = obj.get("entrypoint", "")
                    if not first_user_msg:
                        text = extract_text_from_message(obj.get("message", {}))
                        text = text.strip()
                        if text and not text.startswith("<ide_opened_file>"):
                            first_user_msg = text
                elif msg_type == "assistant":
                    assistant_count += 1

        if started_at is None:
            return None

        session = Session(
            session_id=session_id,
            pid=0,
            cwd=cwd,
            started_at=started_at,
            kind=SessionKind.INTERACTIVE,
            entrypoint=entrypoint,
            jsonl_path=str(jsonl_path),
        )
        session._quick_user_count = user_count
        session._quick_assistant_count = assistant_count
        session._quick_first_msg = first_user_msg
        session._last_at = last_at or started_at
        return session

    except OSError:
        return None


def load_session_meta(session_file: Path) -> Session | None:
    """从 sessions/*.json 加载 session 元数据。"""
    try:
        data = json.loads(session_file.read_text())
        return Session(
            session_id=data["sessionId"],
            pid=data.get("pid", 0),
            cwd=data.get("cwd", ""),
            started_at=datetime.fromtimestamp(data["startedAt"] / 1000),
            kind=SessionKind(data.get("kind", "interactive")),
            entrypoint=data.get("entrypoint", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def load_session_messages(session: Session) -> list[SessionMessage]:
    """从项目的 JSONL 文件加载 session 的对话历史。"""
    # 优先使用已知的 jsonl_path，避免遍历查找
    if session.jsonl_path:
        jsonl_path = Path(session.jsonl_path)
    else:
        proj_dir = find_project_dir(session.session_id)
        if not proj_dir:
            return []
        jsonl_path = proj_dir / f"{session.session_id}.jsonl"
        session.jsonl_path = str(jsonl_path)

    messages: list[SessionMessage] = []
    try:
        with jsonlines.open(jsonl_path) as reader:
            for obj in reader:
                msg_type = obj.get("type", "")
                if msg_type not in ("user", "assistant"):
                    continue

                msg_content = obj.get("message", {})
                text = extract_text_from_message(msg_content)

                messages.append(
                    SessionMessage(
                        uuid=obj.get("uuid", ""),
                        timestamp=parse_timestamp(obj.get("timestamp", "")),
                        session_id=obj.get("sessionId", ""),
                        msg_type=MessageType(msg_type),
                        text=text,
                        cwd=obj.get("cwd", ""),
                        git_branch=obj.get("gitBranch", ""),
                        parent_uuid=obj.get("parentUuid", ""),
                        raw=obj,
                    )
                )
    except (jsonlines.JSONLinesError, OSError):
        pass

    return messages


def find_project_dir(session_id: str) -> Path | None:
    """根据 session_id 查找对应的项目 JSONL 文件。"""
    if not PROJECTS_DIR.exists():
        return None
    for proj_dir in PROJECTS_DIR.iterdir():
        if proj_dir.is_dir():
            jsonl = proj_dir / f"{session_id}.jsonl"
            if jsonl.exists():
                return proj_dir
    return None


def list_all_sessions(project_filter: str = "") -> list[Session]:
    """列出所有 session，扫描 projects 目录下的 JSONL 文件。"""
    if not PROJECTS_DIR.exists():
        return []

    sessions: list[Session] = []
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        project_path = decode_project_path(proj_dir.name)
        if project_filter and project_filter not in project_path:
            continue
        for jsonl_file in proj_dir.glob("*.jsonl"):
            session = load_session_from_jsonl(jsonl_file, project_path)
            if session is None:
                continue
            sessions.append(session)

    sessions.sort(key=lambda s: s.started_at, reverse=True)
    return sessions


def get_session(session_id: str) -> Session | None:
    """根据 session_id 获取完整的 session（含消息历史）。"""
    # 先从 sessions/ 目录查找（有完整元数据如 pid）
    for f in SESSIONS_DIR.glob("*.json"):
        session = load_session_meta(f)
        if session and session.session_id == session_id:
            session.messages = load_session_messages(session)
            return session

    # 再从 projects/ 目录查找
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        jsonl_path = proj_dir / f"{session_id}.jsonl"
        if jsonl_path.exists():
            project_path = decode_project_path(proj_dir.name)
            session = load_session_from_jsonl(jsonl_path, project_path)
            if session:
                session.messages = load_session_messages(session)
                return session

    return None


def search_sessions(keyword: str = "") -> list[Session]:
    """按关键字搜索 session（匹配 session_id 或用户消息内容）。"""
    sessions = list_all_sessions()
    if not keyword:
        return sessions

    results = []
    for session in sessions:
        # 匹配 session_id
        if keyword in session.session_id:
            session.messages = load_session_messages(session)
            results.append(session)
            continue
        # 匹配用户消息内容
        session.messages = load_session_messages(session)
        for msg in session.user_messages:
            if keyword.lower() in msg.text.lower():
                results.append(session)
                break
    return results


def list_projects() -> list[dict]:
    """列出所有项目及其 session 统计。"""
    sessions = list_all_sessions()
    by_project: dict[str, list] = {}
    for s in sessions:
        by_project.setdefault(s.cwd, []).append(s)
    result = []
    for path, proj_sessions in sorted(by_project.items(), key=lambda x: max(
        getattr(s, "_last_at", s.started_at) for s in x[1]), reverse=True):
        latest = max(getattr(s, "_last_at", s.started_at) for s in proj_sessions)
        result.append({
            "path": path,
            "session_count": len(proj_sessions),
            "latest_time": latest,
            "first_session_id": proj_sessions[0].session_id,
        })
    return result


def extract_work_summary(jsonl_path: str, project_path: str = "") -> dict:
    """从 JSONL 文件提取工作摘要（修改的文件、工具调用、关键对话、任务进度）。"""
    result = {
        "files_modified": {},           # {file_path: edit_count}
        "files_created": [],            # [file_path, ...]
        "files_read": set(),            # {file_path, ...} 读取过的文件
        "tool_stats": {},               # {tool_name: count}
        "user_requests": [],            # 过滤后的用户请求
        "assistant_summaries": [],      # assistant 的关键文本回复
        "bash_commands": [],            # 执行的 bash 命令
        "todo_snapshots": [],           # TodoWrite 快照（取每次变更）
        "errors_or_issues": [],         # 错误/问题记录
        "decisions": [],                # 关键决策（从 thinking 中提取）
        "git_actions": [],              # git 操作
    }

    # 追踪 TodoWrite 状态变化
    last_todo_hash = ""
    # 追踪 assistant 连续文本（合并同一轮的多段 text）
    current_assistant_texts = []
    last_msg_type = ""

    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type", "")
                content = obj.get("message", {}).get("content", "")

                # assistant 消息开始时，先 flush 上一轮累积的文本
                if msg_type == "assistant" and last_msg_type != "assistant":
                    _flush_assistant_texts(current_assistant_texts, result)
                    current_assistant_texts = []

                # 提取 tool_use 和 text（主要在 assistant 消息的 content list 中）
                if isinstance(content, list):
                    for item in content:
                        if not isinstance(item, dict):
                            continue

                        item_type = item.get("type", "")

                        if item_type == "tool_use":
                            name = item.get("name", "")
                            inp = item.get("input", {})
                            result["tool_stats"][name] = result["tool_stats"].get(name, 0) + 1

                            fp = inp.get("file_path", inp.get("path", ""))
                            if fp and not fp.startswith("/tmp/") and not fp.startswith("/Users/ljn/.claude/"):
                                if name == "Write":
                                    result["files_created"].append(fp)
                                elif name == "Edit":
                                    result["files_modified"][fp] = result["files_modified"].get(fp, 0) + 1
                                elif name == "Read" or name == "Glob":
                                    result["files_read"].add(fp)

                            if name == "Bash":
                                cmd = inp.get("command", "")
                                if cmd:
                                    _classify_bash_command(cmd, result)

                            if name == "TodoWrite":
                                todos = inp.get("todos", [])
                                if todos:
                                    snapshot = _snapshot_todos(todos)
                                    h = hash(snapshot)
                                    if h != last_todo_hash:
                                        last_todo_hash = h
                                        result["todo_snapshots"].append(snapshot)

                        elif item_type == "text":
                            text = item.get("text", "").strip()
                            if text:
                                current_assistant_texts.append(text)
                                # 检测错误/问题
                                if _is_error_or_issue(text):
                                    result["errors_or_issues"].append(text[:200])

                        elif item_type == "thinking":
                            thinking = item.get("thinking", "").strip()
                            if thinking:
                                _extract_decisions(thinking, result)

                # assistant 消息结束时 flush
                if msg_type != "assistant" and last_msg_type == "assistant":
                    _flush_assistant_texts(current_assistant_texts, result)
                    current_assistant_texts = []

                # 提取用户消息（过滤噪音）
                if msg_type == "user":
                    text = extract_text_from_message({"content": content}).strip()
                    if not text:
                        continue
                    if _is_noise(text):
                        continue
                    result["user_requests"].append(text[:500])

                last_msg_type = msg_type

    except OSError:
        pass

    # flush 剩余
    _flush_assistant_texts(current_assistant_texts, result)

    # 后处理
    result["files_created"] = list(dict.fromkeys(result["files_created"]))
    result["files_read"] = sorted(result["files_read"])
    result["bash_commands"] = list(dict.fromkeys(result["bash_commands"]))[-30:]
    result["assistant_summaries"] = result["assistant_summaries"][-15:]
    result["user_requests"] = result["user_requests"][-50:]
    result["todo_snapshots"] = result["todo_snapshots"][-5:]
    result["errors_or_issues"] = list(dict.fromkeys(result["errors_or_issues"]))[-10:]
    result["decisions"] = list(dict.fromkeys(result["decisions"]))[-10:]

    return result


def _is_noise(text: str) -> bool:
    """判断用户消息是否为噪音。"""
    if not text:
        return True
    noise_prefixes = (
        "<ide_opened_file>", "<local-command", "<command-name>",
        "The user selected the lines", "<ide_selection>",
        "[Request interrupted", "Set model to", "Compacted",
    )
    if any(text.startswith(p) for p in noise_prefixes):
        return True
    noise_exact = ("你好", "好的", "开始", "继续", "好了", "嗯", "行", "ok", "OK", "")
    if text in noise_exact:
        return True
    if text.startswith("/model") or text.startswith("/compact"):
        return True
    if "This session is being continued" in text and len(text) > 200:
        return True
    # skill 展开文本（通常很长且包含系统提示）
    if len(text) > 800 and ("Base directory for this skill" in text or "TRIGGER when:" in text):
        return True
    return False


def _is_error_or_issue(text: str) -> bool:
    """判断文本是否包含错误/问题信息。"""
    # 必须包含明确的错误标记，排除正常的分析性文本
    strong_error_signals = (
        "Traceback", "SyntaxError", "ImportError", "ModuleNotFoundError",
        "Permission denied", "FAILED", "Error:",
    )
    for sig in strong_error_signals:
        if sig in text:
            return True
    # 弱信号：需要同时出现多个才算
    weak_signals = ("error:", "失败", "不存在", "not found", "No such file")
    count = sum(1 for s in weak_signals if s in text)
    return count >= 2


def _classify_bash_command(cmd: str, result: dict):
    """分类 bash 命令并归入对应列表。"""
    cmd_stripped = cmd.strip()
    if not cmd_stripped:
        return

    # git 操作
    if cmd_stripped.startswith("git "):
        subcmd = cmd_stripped.split()[1] if len(cmd_stripped.split()) > 1 else ""
        if subcmd in ("commit", "push", "pull", "checkout", "merge", "rebase", "stash", "branch", "add"):
            result["git_actions"].append(cmd_stripped[:150])
            return

    # 跳过纯查看命令
    skip_prefixes = ("git status", "git diff", "git log", "ls ", "cat ", "head ", "tail ", "wc ", "echo ", "pwd", "which ", "whoami")
    if any(cmd_stripped.startswith(p) for p in skip_prefixes):
        return

    result["bash_commands"].append(cmd_stripped[:200])


def _snapshot_todos(todos: list) -> str:
    """生成 TodoWrite 快照文本。"""
    parts = []
    for t in todos:
        status_icon = {"completed": "x", "in_progress": ">", "pending": " "}.get(t.get("status", ""), " ")
        content = t.get("content", "")
        parts.append(f"[{status_icon}] {content}")
    return "\n".join(parts)


def _extract_decisions(thinking: str, result: dict):
    """从 thinking 中提取关键决策（优先中文）。"""
    decision_keywords = ("决定", "选择", "方案", "策略", "改为", "使用", "采用", "优先", "不如", "改为")
    lines = thinking.split("\n")
    # 先找中文决策
    for line in lines:
        line = line.strip()
        if any(kw in line for kw in decision_keywords):
            if 10 < len(line) < 200:
                result["decisions"].append(line)
                return
    # 没找到中文，找英文决策
    en_keywords = ("decided", "instead of", "approach:", "will use", "going to")
    for line in lines:
        line = line.strip()
        if any(kw in line.lower() for kw in en_keywords):
            if 10 < len(line) < 200:
                result["decisions"].append(line)
                return


def _flush_assistant_texts(texts: list, result: dict):
    """将累积的 assistant 文本合并后提取关键回复。"""
    if not texts:
        return
    combined = "\n".join(texts)
    # 过滤纯代码块和太短的内容
    stripped = combined.strip()
    if len(stripped) < 50:
        return
    # 去掉代码块占比过高的文本
    code_block_len = sum(len(block) for block in stripped.split("```")[1::2])
    if code_block_len > len(stripped) * 0.7:
        # 代码为主的回复，只保留非代码部分
        non_code = stripped.split("```")[0::2]
        text_part = "\n".join(non_code).strip()
        if len(text_part) > 30:
            result["assistant_summaries"].append(text_part[:400])
        return
    result["assistant_summaries"].append(stripped[:400])
