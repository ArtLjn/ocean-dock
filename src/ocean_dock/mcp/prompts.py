"""MCP Prompts — 2 个 prompt 定义"""

from ocean_dock.mcp.server import _dedup_requests, _get_work_summary, _resolve_session
from ocean_dock.utils import short_path, truncate


def register_prompts(server):
    """注册所有 MCP Prompts。"""

    @server.prompt(name="session_handoff")
    def prompt_session_handoff(session_id: str) -> str:
        """生成交接班 prompt，引导 Claude 快速衔接上一个 session 的工作。"""
        from ocean_dock.commands.summary import _generate_context

        session = _resolve_session(session_id)
        if session is None:
            return f"未找到 session: {session_id}，无法生成交接班文档。"

        work = _get_work_summary(session)
        context = _generate_context(session, work)

        return (
            "以下是上一个 session 的交接文档，请仔细阅读并理解当前工作状态，"
            "然后继续完成未完成的任务。\n\n"
            f"---\n\n{context}\n\n---\n\n"
            "请基于以上交接信息，告诉我你理解了哪些内容，以及下一步建议做什么。"
        )

    @server.prompt(name="session_compare")
    def prompt_session_compare(session_id_a: str, session_id_b: str) -> str:
        """对比两个 session，分析差异和关联。"""
        session_a = _resolve_session(session_id_a)
        session_b = _resolve_session(session_id_b)

        if session_a is None:
            return f"未找到 session A: {session_id_a}"
        if session_b is None:
            return f"未找到 session B: {session_id_b}"

        work_a = _get_work_summary(session_a)
        work_b = _get_work_summary(session_b)

        cwd_a, cwd_b = session_a.cwd, session_b.cwd

        def _file_set(work):
            return (
                set(work.get("files_created", []))
                | set(work.get("files_modified", {}).keys())
            )

        set_a, set_b = _file_set(work_a), _file_set(work_b)
        common = set_a & set_b
        only_a = set_a - set_b
        only_b = set_b - set_a

        lines = [
            "## Session 对比分析",
            "",
            f"| | Session A `{session_a.session_id[:8]}` | Session B `{session_b.session_id[:8]}` |",
            "|---|---|---|",
            f"| 项目 | `{short_path(cwd_a)}` | `{short_path(cwd_b)}` |",
            f"| 时间 | {session_a.started_at.strftime('%Y-%m-%d %H:%M') if session_a.started_at else '?'} | {session_b.started_at.strftime('%Y-%m-%d %H:%M') if session_b.started_at else '?'} |",
            f"| 用户请求数 | {len(work_a.get('user_requests', []))} | {len(work_b.get('user_requests', []))} |",
            f"| 文件变更数 | {len(set_a)} | {len(set_b)} |",
            "",
        ]

        if common:
            lines.append("### 共同涉及的文件")
            lines.append("")
            for fp in sorted(common):
                lines.append(f"- `{short_path(fp, cwd_a)}`")
            lines.append("")

        if only_a:
            lines.append("### 仅 Session A 涉及的文件")
            lines.append("")
            for fp in sorted(only_a):
                lines.append(f"- `{short_path(fp, cwd_a)}`")
            lines.append("")

        if only_b:
            lines.append("### 仅 Session B 涉及的文件")
            lines.append("")
            for fp in sorted(only_b):
                lines.append(f"- `{short_path(fp, cwd_b)}`")
            lines.append("")

        # 需求对比
        reqs_a = _dedup_requests(work_a.get("user_requests", []))
        reqs_b = _dedup_requests(work_b.get("user_requests", []))
        if reqs_a or reqs_b:
            lines.append("### 用户需求对比")
            lines.append("")
            if reqs_a:
                lines.append("**Session A 需求：**")
                for r in reqs_a[:10]:
                    lines.append(f"- {truncate(r, 100)}")
                lines.append("")
            if reqs_b:
                lines.append("**Session B 需求：**")
                for r in reqs_b[:10]:
                    lines.append(f"- {truncate(r, 100)}")
                lines.append("")

        lines.append("---")
        lines.append("请基于以上对比信息，分析两个 session 的工作关联性、是否存在冲突或互补关系。")

        return "\n".join(lines)
