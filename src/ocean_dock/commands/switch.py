"""多 Profile 管理 — 一键切换 Claude Code API 套餐"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from ocean_dock.utils import CLAUDE_HOME, safe_write

switch_app = typer.Typer(name="switch", help="管理 Claude Code API Profile")
console = Console()

PROFILES_PATH = CLAUDE_HOME / "profiles.json"


def _load_profiles() -> dict:
    """读取 profiles.json，不存在时返回空结构。"""
    if not PROFILES_PATH.exists():
        return {"current": "", "profiles": {}}
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        # 确保结构完整
        data.setdefault("current", "")
        data.setdefault("profiles", {})
        return data
    except (json.JSONDecodeError, OSError):
        console.print(f"[yellow]警告: {PROFILES_PATH} 格式异常，将重置[/yellow]")
        return {"current": "", "profiles": {}}


def _save_profiles(data: dict) -> None:
    """写入 profiles.json（使用 safe_write 自动备份原文件）。"""
    safe_write(PROFILES_PATH, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _mask_key(key: str) -> str:
    """API Key 脱敏：只显示前 4 位 + ****。"""
    if len(key) <= 4:
        return "****"
    return key[:4] + "****"


@switch_app.callback(invoke_without_command=True)
def switch_default(ctx: typer.Context):
    """列出所有 Profile（等同于 list）"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_profiles)


@switch_app.command("list")
def list_profiles():
    """显示所有 Profile，当前 Profile 标记 *"""
    data = _load_profiles()
    profiles = data.get("profiles", {})
    current = data.get("current", "")

    if not profiles:
        console.print("[dim]暂无 Profile，使用 [bold]ocean-dock switch add <name>[/bold] 添加[/dim]")
        return

    table = Table(title="API Profiles")
    table.add_column("  ", style="bold green", justify="center", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("API Key", style="dim")
    table.add_column("Base URL", style="dim")

    for name, info in profiles.items():
        marker = "[bold green]*[/bold green]" if name == current else " "
        key_display = _mask_key(info.get("api_key", ""))
        base_url = info.get("base_url", "")
        table.add_row(marker, name, key_display, base_url)

    console.print(table)


@switch_app.command("add")
def add_profile(
    name: str = typer.Argument(help="Profile 名称"),
):
    """交互式添加 Profile"""
    data = _load_profiles()
    profiles = data.get("profiles", {})

    if name in profiles:
        overwrite = typer.confirm(f"Profile '{name}' 已存在，是否覆盖？")
        if not overwrite:
            raise typer.Exit(0)

    api_key = typer.prompt("API Key", hide_input=True)
    base_url = typer.prompt("Base URL")

    profiles[name] = {"api_key": api_key, "base_url": base_url}

    # 首次添加时自动设为当前 profile
    if not data.get("current"):
        data["current"] = name

    _save_profiles(data)
    console.print(f"[green]Profile '{name}' 已保存[/green]")


@switch_app.command("use")
def use_profile(
    name: str = typer.Argument(help="Profile 名称"),
):
    """输出 export 命令，配合 eval 使用：eval $(ocean-dock switch use <name>)"""
    data = _load_profiles()
    profiles = data.get("profiles", {})

    if name not in profiles:
        console.print(f"[red]Profile '{name}' 不存在[/red]")
        raise typer.Exit(1)

    info = profiles[name]
    # 纯文本输出，不能用 console.print（避免 ANSI 转义码）
    print(f"export ANTHROPIC_AUTH_TOKEN={info['api_key']}")
    print(f"export ANTHROPIC_BASE_URL={info['base_url']}")

    # 输出 profile 中的额外环境变量（如模型名称等）
    for key, value in info.get("env", {}).items():
        print(f"export {key}={value}")

    # 更新 current
    data["current"] = name
    _save_profiles(data)


@switch_app.command("remove")
def remove_profile(
    name: str = typer.Argument(help="Profile 名称"),
):
    """删除 Profile"""
    data = _load_profiles()
    profiles = data.get("profiles", {})

    if name not in profiles:
        console.print(f"[red]Profile '{name}' 不存在[/red]")
        raise typer.Exit(1)

    confirm = typer.confirm(f"确认删除 Profile '{name}'？")
    if not confirm:
        raise typer.Exit(0)

    del profiles[name]

    # 如果删除的是当前 profile，清除 current
    if data.get("current") == name:
        data["current"] = ""

    _save_profiles(data)
    console.print(f"[green]Profile '{name}' 已删除[/green]")


@switch_app.command("current")
def current_profile():
    """显示当前 Profile 名称"""
    data = _load_profiles()
    current = data.get("current", "")
    # 纯文本输出
    print(current)
