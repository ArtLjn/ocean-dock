"""MCP Tools — 12 个工具定义"""

import subprocess

from ocean_dock.mcp.server import (
    _auto_commit_message,
    _dedup_requests,
    _get_work_summary,
    _resolve_session,
)
from ocean_dock.session_store import (
    list_all_sessions,
    list_projects as _list_projects,
    search_sessions as _search_sessions,
)
from ocean_dock.utils import short_path, truncate


def register_tools(server):
    """注册所有 MCP Tools。"""

    @server.tool()
    def list_sessions(project: str = "", limit: int = 20) -> str:
        """列出 Claude Code 的所有 session，支持按项目路径过滤。

        Args:
            project: 项目路径关键字，用于过滤（可选）
            limit: 返回的最大 session 数量（默认 20）
        """
        sessions = list_all_sessions(project_filter=project)
        sessions = sessions[:limit]

        if not sessions:
            return "没有找到任何 session。"

        lines = []
        for s in sessions:
            user_count = getattr(s, "_quick_user_count", 0)
            assistant_count = getattr(s, "_quick_assistant_count", 0)
            first_msg = getattr(s, "_quick_first_msg", "")
            last_at = getattr(s, "_last_at", s.started_at)
            time_str = last_at.strftime("%m-%d %H:%M") if last_at else ""

            lines.append(f"- **{s.session_id[:8]}** | {time_str} | {user_count}用户/{assistant_count}助手 | {s.cwd}")

            if first_msg:
                lines.append(f"  > {truncate(first_msg, 100)}")

            lines.append("")

        return f"共 {len(sessions)} 个 session：\n\n" + "\n".join(lines)

    @server.tool()
    def show_session(session_id: str) -> str:
        """查看指定 session 的详情（支持前缀匹配）。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)

        if session is None:
            return f"未找到 session: {session_id}"

        lines = []
        lines.append(f"## Session: `{session.session_id}`")
        lines.append("")
        lines.append(f"- **项目路径**: `{session.cwd}`")
        lines.append(f"- **开始时间**: {session.started_at.strftime('%Y-%m-%d %H:%M') if session.started_at else '未知'}")
        lines.append(f"- **消息数**: {len(session.user_messages)} 用户 / {len(session.assistant_messages)} 助手")
        if session.messages:
            lines.append(f"- **时间范围**: {session.time_range}")

        if session.user_messages:
            lines.append("")
            lines.append("### 用户消息")
            lines.append("")
            for i, msg in enumerate(session.user_messages, 1):
                lines.append(f"{i}. [{msg.timestamp}] {truncate(msg.text, 200)}")

        return "\n".join(lines)

    @server.tool()
    def get_session_summary(session_id: str) -> str:
        """为 session 生成交接上下文摘要（Markdown），用于 session 恢复或交接。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        from ocean_dock.commands.summary import _generate_context

        session = _resolve_session(session_id)

        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        return _generate_context(session, work)

    @server.tool()
    def search_sessions(keyword: str) -> str:
        """按关键字搜索 session（匹配 session_id 或用户消息内容）。

        Args:
            keyword: 搜索关键字
        """
        results = _search_sessions(keyword)

        if not results:
            return f"没有找到包含 \"{keyword}\" 的 session。"

        lines = []
        for s in results:
            user_count = len(s.user_messages)
            time_str = s.started_at.strftime("%m-%d %H:%M") if s.started_at else ""
            lines.append(f"- **{s.session_id[:8]}** | {time_str} | {user_count}条用户消息 | {s.cwd}")

            for msg in s.user_messages[:3]:
                if keyword.lower() in msg.text.lower():
                    lines.append(f"  > {truncate(msg.text, 150)}")
                    break

            lines.append("")

        return f"找到 {len(results)} 个匹配的 session：\n\n" + "\n".join(lines)

    @server.tool()
    def get_session_changes(session_id: str) -> str:
        """获取 session 中的文件变更（新建/修改/读取）。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        cwd = session.cwd
        lines = [f"## 文件变更 — `{session.session_id[:8]}`", ""]

        files_created = work.get("files_created", [])
        files_modified = work.get("files_modified", {})
        files_read = work.get("files_read", [])

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

        changed = set(files_modified.keys()) | set(files_created)
        read_only = [f for f in files_read if f not in changed]
        if read_only:
            lines.append("**读取（只读）**:")
            for fp in read_only[:30]:
                lines.append(f"- `{short_path(fp, cwd)}`")
            if len(read_only) > 30:
                lines.append(f"- ... 还有 {len(read_only) - 30} 个")
            lines.append("")

        if not files_created and not files_modified and not read_only:
            lines.append("此 session 没有文件变更记录。")

        return "\n".join(lines)

    @server.tool()
    def get_session_requests(session_id: str) -> str:
        """获取 session 中用户的请求记录（去重后）。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        raw_requests = work.get("user_requests", [])
        deduped = _dedup_requests(raw_requests)

        if not deduped:
            return f"Session `{session_id[:8]}` 没有有效的用户请求记录。"

        lines = [f"## 用户请求 — `{session.session_id[:8]}`", ""]
        for i, req in enumerate(deduped, 1):
            lines.append(f"{i}. {req}")
        lines.append("")
        lines.append(f"*共 {len(deduped)} 条去重请求（原始 {len(raw_requests)} 条）*")

        return "\n".join(lines)

    @server.tool()
    def get_session_todos(session_id: str) -> str:
        """获取 session 中的 TodoWrite 任务进度快照。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        snapshots = work.get("todo_snapshots", [])

        if not snapshots:
            return f"Session `{session_id[:8]}` 没有任务进度记录。"

        lines = [f"## 任务进度 — `{session.session_id[:8]}`", ""]
        for i, snap in enumerate(snapshots, 1):
            label = "最终状态" if i == len(snapshots) else f"快照 {i}"
            lines.append(f"### {label}")
            lines.append("```")
            lines.append(snap)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    @server.tool()
    def get_session_errors(session_id: str) -> str:
        """获取 session 中遇到的错误和问题。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        errors = work.get("errors_or_issues", [])

        if not errors:
            return f"Session `{session_id[:8]}` 没有记录到错误或问题。"

        lines = [f"## 错误与问题 — `{session.session_id[:8]}`", ""]
        for i, e in enumerate(errors, 1):
            lines.append(f"{i}. {truncate(e, 200)}")

        return "\n".join(lines)

    @server.tool()
    def get_session_decisions(session_id: str) -> str:
        """获取 session 中从 thinking 提取的关键决策。

        Args:
            session_id: Session ID，支持前几位匹配
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        work = _get_work_summary(session)
        decisions = work.get("decisions", [])

        if not decisions:
            return f"Session `{session_id[:8]}` 没有提取到关键决策。"

        lines = [f"## 关键决策 — `{session.session_id[:8]}`", ""]
        for i, d in enumerate(decisions, 1):
            lines.append(f"{i}. {d}")

        return "\n".join(lines)

    @server.tool()
    def get_session_conversation(session_id: str, role: str = "all", limit: int = 50) -> str:
        """获取 session 的对话内容，支持按角色过滤。

        Args:
            session_id: Session ID，支持前几位匹配
            role: 过滤角色 — "user" / "assistant" / "all"（默认 all）
            limit: 返回的最大消息条数（默认 50）
        """
        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}"

        messages = session.messages or []
        if role == "user":
            messages = session.user_messages
        elif role == "assistant":
            messages = session.assistant_messages

        messages = messages[-limit:]

        if not messages:
            return f"Session `{session_id[:8]}` 没有匹配的消息。"

        lines = [f"## 对话记录 — `{session.session_id[:8]}` (role={role})", ""]
        for msg in messages:
            role_label = "用户" if msg.msg_type.value == "user" else "助手"
            lines.append(f"**[{role_label}]** [{msg.timestamp}]")
            lines.append(f"{truncate(msg.text, 300)}")
            lines.append("")

        return "\n".join(lines)

    @server.tool()
    def list_projects() -> str:
        """列出所有项目及其 session 统计（按最近活跃时间排序）。"""
        projects = _list_projects()

        if not projects:
            return "没有找到任何项目。"

        lines = [f"共 {len(projects)} 个项目：", ""]
        for p in projects:
            time_str = p["latest_time"].strftime("%m-%d %H:%M") if p["latest_time"] else ""
            lines.append(
                f"- **{short_path(p['path'])}** | {time_str} | "
                f"{p['session_count']} 个 session | `{p['first_session_id'][:8]}`"
            )

        return "\n".join(lines)

    @server.tool()
    def git_commit(message: str = "", cwd: str = "") -> str:
        """提交 git 更改，自动检测变更文件并生成 commit message。

        Args:
            message: 可选的 commit message，为空时自动根据 diff 生成
            cwd: 可选的工作目录，默认当前目录
        """
        import os

        work_dir = cwd or os.getcwd()

        # 检查是否在 git 仓库中
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=work_dir,
        )
        if result.returncode != 0:
            return f"错误：`{work_dir}` 不是 git 仓库。"

        # 获取变更状态
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=work_dir,
        )
        if not status.stdout.strip():
            return "没有需要提交的变更。"

        changed_files = status.stdout.strip().split("\n")

        # 获取 diff 用于生成 message
        diff = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True, text=True, cwd=work_dir,
        )
        unstaged_diff = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True, cwd=work_dir,
        )

        # 自动生成 commit message
        if not message:
            diff_text = diff.stdout or unstaged_diff.stdout
            message = _auto_commit_message(changed_files, diff_text)

        # 如果没有暂存文件，先 add 所有变更
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, cwd=work_dir,
        )
        if not staged.stdout.strip():
            subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, text=True, cwd=work_dir,
            )

        # 提交
        commit = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, cwd=work_dir,
        )

        if commit.returncode != 0:
            return f"提交失败：\n{commit.stderr}"

        # 获取提交结果
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=work_dir,
        )
        return f"提交成功：\n{log.stdout.strip()}\n\n变更文件：\n" + "\n".join(f"- {f}" for f in changed_files)
