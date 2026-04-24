"""列出项目 / session（两级 drill-down）"""

from collections import defaultdict
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ocean_dock.session_store import list_all_sessions
from ocean_dock.utils import truncate

console = Console()


def list_sessions(
    project: Annotated[str, typer.Argument(help="项目编号或路径（展开项目下的 sessions）")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="显示数量")] = 20,
):
    """列出所有 Claude Code 项目或 session

    \b
    示例:
      clm list              查看所有项目
      clm list .            查看当前项目的 sessions
      clm list 1            展开第 1 个项目的 sessions
      clm list airQA        按路径模糊匹配展开
      clm list airQA -n 50  显示 50 条 session
    """
    import os

    # "." 特殊处理：直接用文件系统目录名匹配，避免 decode_project_path 的歧义
    if project == ".":
        from ocean_dock.utils import PROJECTS_DIR, encode_project_path
        from ocean_dock.session_store import load_session_from_jsonl

        cwd = os.getcwd()
        encoded = encode_project_path(cwd)
        proj_dir = PROJECTS_DIR / encoded

        if not proj_dir.exists():
            console.print(f"[yellow]当前项目没有 session 记录: {cwd}[/yellow]")
            return

        sessions = []
        for jsonl_file in proj_dir.glob("*.jsonl"):
            s = load_session_from_jsonl(jsonl_file, cwd)
            if s:
                sessions.append(s)

        if not sessions:
            console.print("[yellow]当前项目没有 session 记录[/yellow]")
            return

        sessions.sort(key=lambda s: getattr(s, "_last_at", s.started_at), reverse=True)
        _show_project_sessions(cwd, sessions, limit)
        return

    all_sessions = list_all_sessions()

    if not all_sessions:
        console.print("[yellow]没有找到 session[/yellow]")
        return

    # 按项目分组
    by_project: dict[str, list] = defaultdict(list)
    for s in all_sessions:
        by_project[s.cwd].append(s)

    sorted_projects = sorted(
        by_project.items(),
        key=lambda x: max(getattr(s, "_last_at", s.started_at) for s in x[1]),
        reverse=True,
    )

    if not project:
        _show_project_list(sorted_projects, len(all_sessions))
    else:
        # 解析目标项目：支持编号或路径模糊匹配
        target_path = _resolve_project(project, sorted_projects)
        if target_path is None:
            console.print(f"[red]未找到匹配的项目: {project}[/red]")
            raise typer.Exit(1)

        proj_sessions = by_project[target_path]
        proj_sessions.sort(key=lambda s: getattr(s, "_last_at", s.started_at), reverse=True)
        _show_project_sessions(target_path, proj_sessions, limit)


def _resolve_project(query: str, sorted_projects: list[tuple[str, list]]) -> str | None:
    """根据编号或路径模糊匹配找到项目路径。"""
    # 编号匹配
    if query.isdigit():
        idx = int(query) - 1
        if 0 <= idx < len(sorted_projects):
            return sorted_projects[idx][0]
        return None

    # 路径模糊匹配
    for path, _ in sorted_projects:
        if query in path:
            return path
    return None


def _show_project_list(sorted_projects: list[tuple[str, list]], total_sessions: int):
    """显示项目概览列表。"""
    table = Table(
        title="Claude Code 项目",
        show_header=True,
        header_style="bold cyan",
        title_style="bold",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("项目路径", max_width=50, no_wrap=True)
    table.add_column("Sessions", justify="right", width=8)
    table.add_column("最后聊天", width=16)

    for i, (path, proj_sessions) in enumerate(sorted_projects, 1):
        latest = max(getattr(s, "_last_at", s.started_at) for s in proj_sessions)
        table.add_row(
            str(i),
            path,
            str(len(proj_sessions)),
            latest.strftime("%m-%d %H:%M"),
        )

    console.print(table)
    console.print(
        f"\n共 [bold]{len(sorted_projects)}[/bold] 个项目，"
        f"[bold]{total_sessions}[/bold] 个 session"
    )
    console.print(
        "使用 [bold]ocean-dock list <编号或路径>[/bold] 展开查看 sessions"
    )


def _show_project_sessions(project_path: str, sessions: list, limit: int):
    """显示项目下的所有 sessions。"""
    display = sessions[:limit]

    console.print(
        f"\n[bold cyan]{project_path}[/bold cyan] "
        f"[dim]({len(sessions)} session{'s' if len(sessions) != 1 else ''})[/dim]"
    )

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Session ID", style="blue", max_width=12, no_wrap=True)
    table.add_column("最后聊天", width=14)
    table.add_column("消息", justify="right", width=5)
    table.add_column("入口", width=8)
    table.add_column("会话名称", max_width=50, no_wrap=True)

    for i, session in enumerate(display, 1):
        msg_count = getattr(session, "_quick_user_count", 0) + getattr(
            session, "_quick_assistant_count", 0
        )
        first_msg = truncate(getattr(session, "_quick_first_msg", ""), 50) or "-"
        ep = session.entrypoint.replace("claude-", "") if session.entrypoint else "-"
        last_at = getattr(session, "_last_at", session.started_at)

        table.add_row(
            str(i),
            session.session_id[:8],
            last_at.strftime("%m-%d %H:%M"),
            str(msg_count),
            ep,
            first_msg,
        )

    console.print(table)

    if len(display) < len(sessions):
        console.print(
            f"[dim]显示 {len(display)}/{len(sessions)} 个，使用 -n 调整数量[/dim]"
        )
