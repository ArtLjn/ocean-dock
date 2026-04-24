"""查看 session 详情"""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ocean_dock.session_store import get_session, list_all_sessions, load_session_messages, search_sessions
from ocean_dock.utils import extract_file_paths, truncate

console = Console()


def show(
    session_id: Annotated[str, typer.Argument(help="Session ID（支持前缀匹配）")],
    search: Annotated[str, typer.Option("--search", "-s", help="按关键字搜索")] = "",
):
    """查看 session 详情

    \b
    示例:
      clm show 6989b              按 session ID 前缀查看
      clm show -s "抢票"          按关键字搜索并查看第一个匹配结果
    """
    if search:
        sessions = search_sessions(search)
        if not sessions:
            console.print(f"[yellow]未找到匹配 '{search}' 的 session[/yellow]")
            return
        session = sessions[0]
    else:
        session = get_session(session_id)
        if session is None:
            for s in list_all_sessions():
                if s.session_id.startswith(session_id):
                    s.messages = load_session_messages(s)
                    session = s
                    break

    if session is None:
        console.print(f"[red]未找到 session: {session_id}[/red]")
        return

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan", width=12)
    info_table.add_column()
    info_table.add_row("Session ID", session.session_id)
    info_table.add_row("PID", str(session.pid))
    info_table.add_row("项目路径", session.cwd)
    info_table.add_row("开始时间", session.started_at.strftime("%Y-%m-%d %H:%M:%S"))
    info_table.add_row("入口", session.entrypoint or "-")
    info_table.add_row("消息统计", f"用户 {len(session.user_messages)} / 助手 {len(session.assistant_messages)}")

    if session.messages:
        git_branch = session.messages[0].git_branch
        if git_branch and git_branch != "HEAD":
            info_table.add_row("Git 分支", git_branch)

    console.print(Panel(info_table, title="Session 详情", border_style="blue"))

    if session.messages:
        console.print("\n[bold]消息时间线[/bold]\n")
        msg_table = Table(show_header=True, header_style="bold", padding=(0, 1))
        msg_table.add_column("#", style="dim", width=3)
        msg_table.add_column("角色", width=6)
        msg_table.add_column("时间", width=16, style="dim")
        msg_table.add_column("内容摘要")

        idx = 0
        for msg in session.messages:
            if not msg.text:
                continue
            idx += 1
            role = "用户" if msg.msg_type.value == "user" else "助手"
            role_style = "green" if msg.msg_type.value == "user" else "yellow"
            summary = truncate(msg.text, 80)
            msg_table.add_row(str(idx), f"[{role_style}]{role}[/{role_style}]", msg.timestamp, summary)

        console.print(msg_table)

        all_files = set()
        for msg in session.user_messages:
            all_files.update(extract_file_paths(msg.text))
        for msg in session.assistant_messages:
            all_files.update(extract_file_paths(msg.text))

        if all_files:
            console.print(f"\n[bold]涉及的文件[/bold] ({len(all_files)} 个)")
            for f in sorted(all_files)[:20]:
                console.print(f"  [dim]-[/dim] {f}")
            if len(all_files) > 20:
                console.print(f"  [dim]... 还有 {len(all_files) - 20} 个文件[/dim]")
