"""为 session 生成交接上下文摘要"""

from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ocean_dock.session_store import (
    extract_work_summary,
    get_session,
    list_all_sessions,
    load_session_messages,
)
from ocean_dock.utils import short_path, truncate, load_config

console = Console()


def summary(
    session_id: Annotated[str, typer.Argument(help="Session ID（支持前缀匹配）")],
    output: Annotated[str, typer.Option("--output", "-o", help="输出到文件")] = "",
    copy: Annotated[bool, typer.Option("--copy", "-c", help="复制到剪贴板")] = False,
    handoff: Annotated[bool, typer.Option("--handoff", "-r", help="生成摘要后直接进入新 session，以摘要作为初始 prompt")] = False,
):
    """为 session 生成交接上下文，便于下一个 session 快速衔接工作

    \b
    示例:
      clm summary 6989b           打印摘要到终端
      clm summary 6989b -o ctx.md 保存到文件
      clm summary 6989b -c        复制到剪贴板
      clm summary 6989b -r        生成摘要并直接进入新 session

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

    # 从 JSONL 提取工作摘要
    jsonl_path = session.jsonl_path
    work = extract_work_summary(jsonl_path, session.cwd) if jsonl_path else {}

    content = _generate_context(session, work)

    if handoff:
        import subprocess as sp
        import shutil
        # 构造交接 prompt：用摘要作为新 session 的初始 prompt
        handoff_prompt = f"{content}\n\n/session-handoff"
        work_dir = session.cwd if session.cwd else None

        config = load_config()
        cli_command = config.get("cli_command", "claude")
        claude_bin = shutil.which(cli_command)
        if claude_bin is None:
            console.print(f"[red]未找到 {cli_command} 命令，请确保 Claude Code CLI 已安装[/red]")
            console.print("[dim]提示: 可以通过配置 ocean-dock.json 中的 cli_command 字段修改使用的命令名称[/dim]")
            raise typer.Exit(1)

        cmd = [claude_bin, handoff_prompt]
        console.print("\n[bold green]正在启动新 session...[/bold green]")
        console.print(f"[dim]工作目录: {work_dir}[/dim]\n")
        try:
            sp.run(cmd, cwd=work_dir)
        except FileNotFoundError:
            console.print(f"[red]未找到 {cli_command} 命令，请确保 Claude Code CLI 已安装[/red]")
            raise typer.Exit(1)
        return

    if output:
        from pathlib import Path
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]已保存到 {output}[/green]")
    elif copy:
        import subprocess
        try:
            subprocess.run(["pbcopy"], input=content, text=True, check=True)
            console.print("[green]已复制到剪贴板[/green]")
        except FileNotFoundError:
            console.print("[red]pbcopy 不可用，请手动复制[/red]")
            console.print(content)
    else:
        console.print(Panel(Markdown(content), title="Session 上下文交接", border_style="green"))


def _generate_context(session, work: dict) -> str:
    """生成交接上下文文档。"""
    lines: list[str] = []
    cwd = session.cwd

    # 基本信息
    lines.append(f"## 项目: `{cwd}`")
    if session.messages:
        git_branch = session.messages[0].git_branch
        if git_branch and git_branch != "HEAD":
            lines.append(f"**Git 分支**: {git_branch}")
    if session.started_at:
        lines.append(f"**时间**: {session.started_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 用户需求记录（最重要的信息放前面）
    user_requests = work.get("user_requests", [])
    if user_requests:
        lines.append("### 用户需求记录")
        lines.append("")
        # 去重（相似文本只保留第一次）
        seen = []
        for req in user_requests:
            clean = _clean_user_text(req)
            if not clean:
                continue
            # 跳过和已见过的文本高度相似的
            if any(_similarity(clean, s) > 0.8 for s in seen):
                continue
            seen.append(clean)
        for i, req in enumerate(seen, 1):
            lines.append(f"{i}. {req}")
        lines.append("")

    # 已完成的工作
    files_modified = work.get("files_modified", {})
    files_created = work.get("files_created", [])
    files_read = work.get("files_read", [])
    tool_stats = work.get("tool_stats", {})

    if files_modified or files_created:
        lines.append("### 文件变更")
        lines.append("")

        if files_created:
            lines.append("**新建**:")
            for fp in files_created:
                lines.append(f"- `{short_path(fp, cwd)}`")
            lines.append("")

        if files_modified:
            lines.append("**修改**:")
            for fp, count in sorted(files_modified.items(), key=lambda x: -x[1]):
                lines.append(f"- `{short_path(fp, cwd)}` ({count} 次编辑)")
            lines.append("")

        # 工作量统计
        edits = sum(files_modified.values())
        writes = len(files_created)
        reads = tool_stats.get("Read", 0)
        bash_count = tool_stats.get("Bash", 0)
        lines.append(f"**工作量**: {writes} 新建, {edits} 编辑, {reads} 读取, {bash_count} 命令执行")
        lines.append("")

    # 任务进度
    todo_snapshots = work.get("todo_snapshots", [])
    if todo_snapshots:
        # 取最后一个快照作为当前状态
        final_snapshot = todo_snapshots[-1]
        lines.append("### 任务进度（最终状态）")
        lines.append("")
        lines.append("```")
        lines.append(final_snapshot)
        lines.append("```")
        lines.append("")

    # 关键结论和分析
    assistant_summaries = work.get("assistant_summaries", [])
    if assistant_summaries:
        lines.append("### 关键结论与分析")
        lines.append("")
        for i, text in enumerate(assistant_summaries[-8:], 1):
            lines.append(f"**[{i}]** {truncate(text, 400)}")
            lines.append("")

    # 关键决策
    decisions = work.get("decisions", [])
    if decisions:
        lines.append("### 关键决策")
        lines.append("")
        for d in decisions[-8:]:
            lines.append(f"- {d}")
        lines.append("")

    # 遇到的问题
    errors = work.get("errors_or_issues", [])
    if errors:
        lines.append("### 遇到的问题")
        lines.append("")
        for e in errors:
            lines.append(f"- {truncate(e, 150)}")
        lines.append("")

    # Git 操作
    git_actions = work.get("git_actions", [])
    if git_actions:
        lines.append("### Git 操作")
        lines.append("")
        for g in git_actions[-10:]:
            lines.append(f"- `{g}`")
        lines.append("")

    # 执行的命令（非 git、非查看）
    bash_commands = work.get("bash_commands", [])
    if bash_commands:
        lines.append("### 关键命令")
        lines.append("")
        for cmd in bash_commands[-15:]:
            lines.append(f"- `{cmd}`")
        lines.append("")

    # 涉及的文件（读取过的）
    if files_read:
        # 排除已修改/创建的文件
        changed = set(files_modified.keys()) | set(files_created)
        read_only = [f for f in files_read if f not in changed]
        if read_only:
            lines.append("### 参考文件（只读）")
            lines.append("")
            for fp in read_only[:20]:
                lines.append(f"- `{short_path(fp, cwd)}`")
            if len(read_only) > 20:
                lines.append(f"- ... 还有 {len(read_only) - 20} 个")
            lines.append("")

    lines.append("---")
    stats_parts = [f"{len(user_requests)} 条需求"]
    if files_modified or files_created:
        stats_parts.append(f"{len(files_created)} 新建, {sum(files_modified.values())} 编辑")
    lines.append(f"*Session `{session.session_id[:8]}` | {' | '.join(stats_parts)}*")

    return "\n".join(lines)



def _clean_user_text(text: str) -> str:
    """清理用户消息文本。"""
    import re
    # 去掉 IDE 标签
    text = re.sub(r"<[^>]+>", "", text).strip()
    # 去掉多余空行
    text = re.sub(r"\n{2,}", "\n", text)
    # 截断过长文本
    if len(text) > 300:
        text = text[:300] + "..."
    return text


def _similarity(a: str, b: str) -> float:
    """简单的文本相似度（基于公共子序列比例）。"""
    if not a or not b:
        return 0.0
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    if len(shorter) < 10:
        return 1.0 if shorter == longer[:len(shorter)] else 0.0
    # 取较短文本的前 50 字符做前缀匹配
    return 1.0 if shorter[:50] in longer else 0.0
