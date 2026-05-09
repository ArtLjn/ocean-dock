"""一键配置 MCP + Skill + Hooks + 防污染 到当前项目"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from ocean_dock.utils import safe_write

console = Console()

# 项目根目录（src/ocean_dock/commands/ → ../../../）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# hook 脚本目录（项目根目录下的 hooks/）
_HOOKS_DIR = _PROJECT_ROOT / "hooks"

# 模板目录（项目根目录下的 templates/）
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"


def _resolve_clm_bin() -> str:
    """获取 ocean-dock 的可执行文件绝对路径，确保任何环境下都能找到。"""
    if sys.executable:
        venv_bin = Path(sys.executable).parent / "ocean-dock"
        if venv_bin.exists():
            return str(venv_bin)
    which = shutil.which("ocean-dock")
    if which:
        return which
    return "ocean-dock"


def _build_hooks_config() -> dict:
    """构建完整的 hooks 配置（7 个事件类型，含防污染）。"""
    hooks_dir = _HOOKS_DIR
    return {
        "hooks": {
            "Notification": [
                {
                    "matcher": "permission_prompt",
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'notify.sh'}"}],
                },
                {
                    "matcher": "idle_prompt",
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'notify.sh'}"}],
                },
            ],
            "SessionStart": [
                {
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'session_start.sh'}"}],
                },
            ],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'guard_bash.sh'}"}],
                },
                {
                    "matcher": "Write|Edit",
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'guard_write.sh'}"}],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'auto_check.sh'}"}],
                },
            ],
            "PreCompact": [
                {
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'pre_compact.sh'}"}],
                },
            ],
            "Stop": [
                {
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'stop.sh'}"}],
                },
                {
                    "hooks": [{"type": "command", "command": f"bash {hooks_dir / 'cleanup_stop.sh'}"}],
                },
            ],
        },
    }


def _merge_hooks_into_settings(settings_path: Path) -> None:
    """将 hooks 配置合并写入 .claude/settings.json（不覆盖已有配置）。"""
    # 读取已有配置
    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            console.print(f"  [yellow]警告: {settings_path} 格式异常，将覆盖[/yellow]")

    # 构建 hooks 配置
    hooks_config = _build_hooks_config()

    # 合并：hooks 部分整体替换（因为 hook 列表是完整的）
    if "hooks" in existing:
        # 合并各事件类型，已有的事件追加新 hook，不覆盖
        new_hooks = hooks_config["hooks"]
        for event, entries in new_hooks.items():
            if event not in existing["hooks"]:
                existing["hooks"][event] = entries
            else:
                # 对已有事件类型，追加新的 matcher/hook（按 matcher 去重）
                existing_entries = existing["hooks"][event]
                for entry in entries:
                    matcher = entry.get("matcher", "__no_matcher__")
                    found = False
                    for ex in existing_entries:
                        if ex.get("matcher") == matcher:
                            # 合并 hooks 列表（按 command 去重）
                            ex_cmds = {h.get("command", "") for h in ex.get("hooks", [])}
                            for h in entry.get("hooks", []):
                                if h.get("command", "") not in ex_cmds:
                                    ex.setdefault("hooks", []).append(h)
                            found = True
                            break
                    if not found:
                        existing_entries.append(entry)
    else:
        existing["hooks"] = hooks_config["hooks"]

    # 写回（使用 safe_write 自动备份原文件）
    safe_write(settings_path, json.dumps(existing, indent=2, ensure_ascii=False) + "\n")


def init(
    project_dir: str = typer.Argument("", help="目标项目路径（默认当前目录）"),
    scope: str = typer.Option("user", "-s", "--scope", help="MCP 注册范围: user（全局）或 local（项目级）"),
    harness: bool = typer.Option(True, "--harness/--no-harness", help="是否同时初始化 Harness Engineering"),
    tech_stack: str = typer.Option("both", "-t", "--tech-stack", help="技术栈: python / ts / both"),
    backend_dir: str = typer.Option("backend", "--backend-dir", help="后端目录名"),
    frontend_dir: str = typer.Option("frontend", "--frontend-dir", help="前端目录名"),
):
    """一键配置 MCP + Skill + Hooks + Harness

    注册 MCP Server、复制 Skill、写入 Hooks、配置 Git，并可同时搭建
    Harness Engineering 基础设施（CLAUDE.md、docs/、scripts/、agents、CI）。

    \b
    示例:
      dock init                          完整配置（含 Harness）
      dock init --no-harness             仅配置 ocean-dock，不搭建 Harness
      dock init -t python                纯 Python 项目
      dock init /path/to/project         指定目录
    """
    target = Path(project_dir).resolve() if project_dir else Path.cwd()
    claude_dir = target / ".claude"
    clm_bin = _resolve_clm_bin()

    # ---- 1. 用 claude mcp add 注册 MCP Server ----
    console.print("[bold]注册 MCP Server...[/bold]")
    try:
        result = subprocess.run(
            ["claude", "mcp", "add", "-s", scope, "ocean-dock", "--", clm_bin, "serve"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            console.print(f"  [green]MCP Server 注册成功 ({scope})[/green]")
        else:
            console.print(f"  [yellow]MCP Server 注册跳过: {result.stderr.strip()}[/yellow]")
    except FileNotFoundError:
        console.print("  [yellow]未找到 claude 命令，请手动运行:[/yellow]")
        console.print(f"  [dim]claude mcp add -s {scope} ocean-dock -- {clm_bin} serve[/dim]")
    except subprocess.TimeoutExpired:
        console.print("  [yellow]claude mcp add 超时[/yellow]")

    # ---- 2. 复制 Skill ----
    console.print("[bold]配置 Skill...[/bold]")
    skills_dir = claude_dir / "skills"
    skills_src_dir = _PROJECT_ROOT / "skills"

    if skills_src_dir.is_dir():
        skills_dir.mkdir(parents=True, exist_ok=True)
        copied_count = 0
        for skill_file in skills_src_dir.glob("*.md"):
            dst = skills_dir / skill_file.name
            if not dst.exists():
                shutil.copy2(skill_file, dst)
                copied_count += 1
        if copied_count:
            console.print(f"  [green]已复制 {copied_count} 个 skill 到 {skills_dir}/[/green]")
        else:
            console.print("  [dim]Skill 文件已存在[/dim]")
    else:
        console.print(f"  [yellow]警告: 未找到 skills/ 目录 ({skills_src_dir})[/yellow]")

    # ---- 3. 写入 Hooks 配置 ----
    console.print("[bold]配置 Hooks...[/bold]")
    settings_path = claude_dir / "settings.json"

    # 检查 hook 脚本是否存在
    hook_scripts = [
        "notify.sh", "session_start.sh", "guard_bash.sh", "guard_write.sh",
        "auto_check.sh", "pre_compact.sh", "stop.sh", "cleanup_stop.sh",
    ]
    missing = [s for s in hook_scripts if not (_HOOKS_DIR / s).exists()]
    if missing:
        console.print(f"  [yellow]警告: 以下 hook 脚本不存在: {', '.join(missing)}[/yellow]")
        console.print("  [dim]跳过 hooks 配置[/dim]")
    else:
        _merge_hooks_into_settings(settings_path)
        hook_count = len(hook_scripts)
        console.print(f"  [green]已写入 {hook_count} 个 hooks 到 {settings_path}[/green]")
        console.print("    - Notification: 权限提示/空闲提醒时播放声音")
        console.print("    - SessionStart: 自动加载项目最近 session 摘要")
        console.print("    - PreToolUse+Bash: 拦截危险命令 (rm -rf /, force push 等)")
        console.print("    - PreToolUse+Write/Edit: 阻断垃圾文件写入 (.pyc, .DS_Store 等)")
        console.print("    - PostToolUse+Edit/Write: 文件修改后自动 lint 检查")
        console.print("    - PreCompact: 上下文压缩前保留关键信息")
        console.print("    - Stop: session 结束时保存交接摘要 + 自动清理垃圾文件")

    # ---- 4. Git 初始化 + .gitignore ----
    console.print("[bold]配置 Git...[/bold]")
    git_dir = target / ".git"

    if not git_dir.exists():
        try:
            subprocess.run(["git", "init", str(target)], capture_output=True, text=True, timeout=10)
            console.print("  [green]Git 仓库已初始化[/green]")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            console.print("  [yellow]Git 初始化失败[/yellow]")
    else:
        console.print("  [dim]Git 仓库已存在[/dim]")

    # 复制 .gitignore
    gitignore_src = _TEMPLATES_DIR / ".gitignore"
    gitignore_dst = target / ".gitignore"
    if gitignore_src.exists() and not gitignore_dst.exists():
        shutil.copy2(gitignore_src, gitignore_dst)
        console.print("  [green]已创建 .gitignore[/green]")
    elif gitignore_dst.exists():
        console.print("  [dim].gitignore 已存在[/dim]")

    # ---- 5. .githooks 配置 ----
    console.print("[bold]配置 Git Hooks...[/bold]")
    githooks_src = _TEMPLATES_DIR / ".githooks"
    githooks_dst = target / ".githooks"

    if githooks_src.is_dir():
        copied_hooks = 0
        for hook_file in githooks_src.iterdir():
            if hook_file.is_file():
                dst = githooks_dst / hook_file.name
                if not dst.exists():
                    githooks_dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(hook_file, dst)
                    dst.chmod(0o755)
                    copied_hooks += 1
        if copied_hooks:
            console.print(f"  [green]已创建 {copied_hooks} 个 git hooks[/green]")
            console.print("    - pre-commit: 垃圾文件检测 + 敏感信息检测 + ruff check")
            console.print("    - commit-msg: Conventional Commits 格式校验（仅警告）")
            console.print("    - post-checkout: 切换分支后清理 __pycache__")
            console.print("    - pre-push: 推送前运行 pytest（可选）")
        else:
            console.print("  [dim]git hooks 已存在[/dim]")

        # 启用自定义 hooks 路径
        try:
            subprocess.run(
                ["git", "-C", str(target), "config", "core.hooksPath", ".githooks"],
                capture_output=True, text=True, timeout=5,
            )
            console.print("  [green]已启用 core.hooksPath=.githooks[/green]")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            console.print("  [yellow]git config 设置失败[/yellow]")
    else:
        console.print(f"  [yellow]未找到 githooks 模板 ({githooks_src})[/yellow]")

    # ---- 汇总 ----
    console.print("\n[bold green]配置完成![/bold green]")
    console.print(f"  ocean-dock: {clm_bin}")
    console.print(f"  MCP scope: {scope}")
    console.print("  Git hooks: pre-commit / commit-msg / post-checkout / pre-push")
    console.print("  防污染: guard_write + cleanup_stop")

    # ---- 6. Harness Engineering ----
    if harness:
        console.print("\n[bold]配置 Harness Engineering...[/bold]")
        if tech_stack not in ("python", "ts", "both"):
            console.print(f"  [yellow]无效技术栈: {tech_stack}，跳过 Harness[/yellow]")
        else:
            from ocean_dock.harness import init_harness as _init_harness

            result = _init_harness(
                project_dir=target,
                project_name=target.name,
                tech_stack=tech_stack,
                backend_dir=backend_dir,
                frontend_dir=frontend_dir,
                on_log=lambda msg: console.print(msg),
            )
            console.print(f"  [green]已生成 {result['total_created']} 个 Harness 文件[/green]")

    console.print("\n[dim]重启 Claude Code 后生效，输入 /mcp 确认连接状态[/dim]")
