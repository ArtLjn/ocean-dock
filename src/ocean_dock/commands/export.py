"""导出 session"""

from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console

from ocean_dock.session_store import (
    get_session,
    list_all_sessions,
    load_session_messages,
)
from ocean_dock.utils import extract_file_paths, truncate

console = Console()


def export(
    session_id: Annotated[
        str, typer.Argument(help="Session ID（支持前缀匹配），不传则导出列表")
    ] = "",
    fmt: Annotated[str, typer.Option("--format", "-f", help="导出格式: md 或 json")] = "md",
    output: Annotated[str, typer.Option("--output", "-o", help="输出文件路径（默认输出到 stdout）")] = "",
    project: Annotated[str, typer.Option("--project", "-p", help="按项目路径过滤")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="导出数量")] = 50,
):
    """导出 session

    \b
    示例:
      clm export                        导出全部 session 到终端 (Markdown)
      clm export -o overview.md         导出为 Markdown 文件
      clm export -f json -o out.json    导出为 JSON 文件
      clm export -p airQA -n 10 -o qa.md  导出指定项目的最近 10 条
      clm export 6989b                  导出指定 session
      clm export 6989b -o s.md          导出指定 session 到文件
    """
    from pathlib import Path

    if session_id:
        # 导出指定 session
        session = _resolve_session(session_id)
        if session is None:
            console.print(f"[red]未找到 session: {session_id}[/red]")
            raise typer.Exit(1)
        session.messages = load_session_messages(session)
        sessions = [session]
    else:
        # 导出 session 列表
        sessions = list_all_sessions(project_filter=project)[:limit]
        if not sessions:
            console.print("[yellow]没有找到 session[/yellow]")
            return
        for s in sessions:
            s.messages = load_session_messages(s)

    if fmt == "json":
        content = _export_json(sessions)
    else:
        content = _export_markdown(sessions)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]已导出到 {output}[/green]")
    else:
        console.print(content)


def _resolve_session(session_id: str):
    """根据 session ID（支持前缀匹配）查找 session。"""
    session = get_session(session_id)
    if session:
        return session
    for s in list_all_sessions():
        if s.session_id.startswith(session_id):
            return s
    return None


def _export_markdown(sessions) -> str:
    if len(sessions) == 1:
        return _export_single_markdown(sessions[0])

    lines = [
        "# Claude Code Session 概览",
        "",
        f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Session 总数: {len(sessions)}",
        "",
    ]

    for i, s in enumerate(sessions, 1):
        lines.append(f"## {i}. Session `{s.session_id}`")
        lines.append("")
        lines.append(f"- **项目路径**: `{s.cwd}`")
        lines.append(f"- **开始时间**: {s.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **入口**: {s.entrypoint or '-'}")
        lines.append(f"- **消息数**: 用户 {len(s.user_messages)} / 助手 {len(s.assistant_messages)}")
        if s.first_user_message:
            lines.append(f"- **初始任务**: {truncate(s.first_user_message, 100)}")
        lines.append("")

        all_files = set()
        for msg in s.user_messages:
            all_files.update(extract_file_paths(msg.text))
        if all_files:
            lines.append("  **涉及文件**:")
            for f in sorted(all_files)[:10]:
                lines.append(f"  - `{f}`")
            if len(all_files) > 10:
                lines.append(f"  - ... 还有 {len(all_files) - 10} 个")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _export_single_markdown(s) -> str:
    """导出单个 session 的完整对话记录。"""
    lines = [
        f"# Session `{s.session_id}`",
        "",
        f"- **项目路径**: `{s.cwd}`",
        f"- **开始时间**: {s.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **入口**: {s.entrypoint or '-'}",
        f"- **消息数**: 用户 {len(s.user_messages)} / 助手 {len(s.assistant_messages)}",
    ]

    if s.messages:
        git_branch = s.messages[0].git_branch
        if git_branch and git_branch != "HEAD":
            lines.append(f"- **Git 分支**: {git_branch}")

    lines.append("")

    # 对话记录
    lines.append("## 对话记录")
    lines.append("")
    for msg in s.messages:
        if not msg.text:
            continue
        role = "## User" if msg.msg_type.value == "user" else "## Assistant"
        lines.append(f"**{role}** [{msg.timestamp}]")
        lines.append("")
        lines.append(msg.text)
        lines.append("")
        lines.append("---")
        lines.append("")

    # 涉及的文件
    all_files = set()
    for msg in s.user_messages:
        all_files.update(extract_file_paths(msg.text))
    for msg in s.assistant_messages:
        all_files.update(extract_file_paths(msg.text))
    if all_files:
        lines.append("## 涉及的文件")
        lines.append("")
        for f in sorted(all_files):
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)


def _export_json(sessions) -> str:
    import json

    data = {
        "exported_at": datetime.now().isoformat(),
        "total_sessions": len(sessions),
        "sessions": [s.to_dict() for s in sessions],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
