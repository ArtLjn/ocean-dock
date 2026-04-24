"""恢复 session — 生成上下文摘要并恢复"""

from typing import Annotated

import os
import shutil
import subprocess

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ocean_dock.session_store import get_session, list_all_sessions, load_session_messages
from ocean_dock.utils import extract_file_paths, truncate, load_config

console = Console()


def _generate_summary(session) -> str:
    lines: list[str] = []

    lines.append(f"## 项目: `{session.cwd}`")
    lines.append("")

    if session.first_user_message:
        lines.append("### 初始任务")
        lines.append(session.first_user_message)
        lines.append("")

    if session.user_messages:
        lines.append("### 对话摘要")
        for i, msg in enumerate(session.user_messages):
            text = msg.text.strip()
            if not text or text == session.first_user_message:
                continue
            lines.append(f"**[{i + 1}]** {truncate(text, 150)}")
        lines.append("")

    all_files = set()
    for msg in session.user_messages:
        all_files.update(extract_file_paths(msg.text))
    for msg in session.assistant_messages:
        all_files.update(extract_file_paths(msg.text))

    if all_files:
        lines.append("### 涉及的文件")
        for f in sorted(all_files):
            lines.append(f"- `{f}`")
        lines.append("")

    lines.append("---")
    lines.append(f"*共 {len(session.user_messages)} 条用户消息, {len(session.assistant_messages)} 条助手回复*")

    return "\n".join(lines)


def resume(
    session_id: Annotated[str, typer.Argument(help="Session ID（支持前缀匹配）")],
    summary_only: Annotated[bool, typer.Option("--summary-only", "-s", help="仅打印摘要，不执行恢复")] = False,
    fork: Annotated[bool, typer.Option("--fork", "-f", help="以 fork 模式恢复（创建新 session）")] = False,
):
    """恢复 session，打印上下文摘要后继续对话

    \b
    示例:
      clm resume 6989b           直接恢复 session
      clm resume 6989b -s        仅打印摘要，不恢复
      clm resume 6989b -f        fork 模式（基于旧 session 创建新对话）

    \b
    配置:
      使用 clm config cli_command <name> 可以修改使用的 Claude CLI 命令名称
      例如: clm config cli_command clmg
    """
    session = get_session(session_id)
    if session is None:
        for s in list_all_sessions():
            if s.session_id.startswith(session_id):
                s.messages = load_session_messages(s)
                session = s
                break

    if session is None:
        console.print(f"[red]未找到 session: {session_id}[/red]")
        raise typer.Exit(1)

    summary = _generate_summary(session)
    console.print(Panel(Markdown(summary), title="Session 上下文摘要", border_style="green"))

    if summary_only:
        console.print("\n[dim]提示: 可以将上面的摘要复制到新 session 中，帮助 Claude 理解之前的上下文[/dim]")
        return

    config = load_config()
    cli_command = config.get("cli_command", "claude")
    claude_bin = shutil.which(cli_command)
    if claude_bin is None:
        console.print(f"[red]未找到 {cli_command} 命令，请确保 Claude Code CLI 已安装[/red]")
        console.print("[dim]提示: 可以通过配置 ocean-dock.json 中的 cli_command 字段修改使用的命令名称[/dim]")
        raise typer.Exit(1)

    cmd = [claude_bin, "--resume", session.session_id]
    if fork:
        cmd.append("--fork-session")

    work_dir = session.cwd if session.cwd else None

    if work_dir and not os.path.isdir(work_dir):
        console.print(f"[yellow]工作目录不存在: {work_dir}，正在临时创建...[/yellow]")
        os.makedirs(work_dir, exist_ok=True)

    console.print("\n[bold green]正在恢复 session...[/bold green]")
    console.print(f"[dim]执行命令: {' '.join(cmd)}[/dim]")
    if work_dir:
        console.print(f"[dim]工作目录: {work_dir}[/dim]\n")

    try:
        subprocess.run(cmd, cwd=work_dir)
    except FileNotFoundError:
        console.print(f"[red]未找到 claude 命令: {claude_bin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]恢复失败: {e}[/red]")
        raise typer.Exit(1)
