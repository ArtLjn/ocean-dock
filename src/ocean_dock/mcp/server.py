"""MCP Server 实例与注册框架"""

from mcp.server.fastmcp import FastMCP

from ocean_dock.session_store import (
    extract_work_summary,
    get_session,
    list_all_sessions,
    load_session_messages,
)

# 默认实例（stdio 模式使用）
mcp = FastMCP("ocean-dock")


def _resolve_session(session_id: str):
    """根据 session_id 查找 session（支持前缀匹配），返回 Session 或 None。"""
    session = get_session(session_id)
    if session is None:
        for s in list_all_sessions():
            if s.session_id.startswith(session_id):
                s.messages = load_session_messages(s)
                return s
    return session


def _get_work_summary(session) -> dict:
    """提取 session 的工作摘要。"""
    jsonl_path = session.jsonl_path
    return extract_work_summary(jsonl_path, session.cwd) if jsonl_path else {}


def _dedup_requests(requests: list) -> list[str]:
    """对用户请求做简单去重。"""
    from ocean_dock.commands.summary import _clean_user_text, _similarity
    seen = []
    for req in requests:
        clean = _clean_user_text(req)
        if not clean:
            continue
        if any(_similarity(clean, s) > 0.8 for s in seen):
            continue
        seen.append(clean)
    return seen


def _auto_commit_message(changed_files: list[str], diff_text: str) -> str:
    """根据变更文件和 diff 自动生成 commit message。"""
    added = []
    modified = []
    deleted = []

    for line in changed_files:
        status, path = line[:2], line[3:]
        if status == "A" or status == "??":
            added.append(path)
        elif status == "D":
            deleted.append(path)
        elif status in ("M", "MM", " M", "AM"):
            modified.append(path)

    parts = []
    if added:
        parts.append(f"新增 {', '.join(added[:3])}")
    if modified:
        parts.append(f"修改 {', '.join(modified[:3])}")
    if deleted:
        parts.append(f"删除 {', '.join(deleted[:3])}")

    msg = "；".join(parts)
    if len(msg) > 72:
        msg = msg[:69] + "..."
    return msg


def register_tools(server: FastMCP):
    """将所有 MCP Tools / Resources / Prompts 注册到指定的 FastMCP 实例上。"""
    from ocean_dock.mcp.tools import register_tools as _reg_tools
    from ocean_dock.mcp.resources import register_resources as _reg_resources
    from ocean_dock.mcp.prompts import register_prompts as _reg_prompts

    _reg_tools(server)
    _reg_resources(server)
    _reg_prompts(server)


# 注册到默认实例
register_tools(mcp)
