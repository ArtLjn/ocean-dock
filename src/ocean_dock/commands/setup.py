"""全局一键配置/卸载：安装 dock 命令 + 注册 MCP Server"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()

# 用户本地 bin 目录
LOCAL_BIN = Path.home() / ".local" / "bin"

# 全局 Claude 配置文件
CLAUDE_JSON = Path.home() / ".claude.json"


def _resolve_bin() -> str:
    """获取 ocean-dock 可执行文件绝对路径。"""
    if sys.executable:
        venv_bin = Path(sys.executable).parent / "ocean-dock"
        if venv_bin.exists():
            return str(venv_bin)
    which = shutil.which("ocean-dock")
    if which:
        return which
    return "ocean-dock"


def _install_dock_command(bin_path: str) -> None:
    """安装 dock 全局命令到 ~/.local/bin/。"""
    LOCAL_BIN.mkdir(parents=True, exist_ok=True)
    dock_script = LOCAL_BIN / "dock"

    script_content = f"#!/bin/bash\nexec {bin_path} \"$@\"\n"
    dock_script.write_text(script_content)
    dock_script.chmod(0o755)

    console.print(f"  [green]已安装 [bold]dock[/bold] → {bin_path}[/green]")
    console.print(f"  [dim]{dock_script}[/dim]")


def _register_mcp_global(bin_path: str) -> None:
    """在 ~/.claude.json 中注册 ocean-dock MCP Server。"""
    if not CLAUDE_JSON.exists():
        data = {}
    else:
        try:
            data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            console.print(f"  [yellow]警告: {CLAUDE_JSON} 格式异常[/yellow]")
            data = {}

    mcp_servers = data.setdefault("mcpServers", {})

    existing = mcp_servers.get("ocean-dock", {})
    new_config = {
        "type": "stdio",
        "command": bin_path,
        "args": ["serve"],
    }

    if existing.get("command") == bin_path and existing.get("args") == ["serve"]:
        console.print("  [dim]MCP Server 已注册，无需更新[/dim]")
        return

    mcp_servers["ocean-dock"] = new_config
    CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print("  [green]已注册 [bold]ocean-dock[/bold] MCP Server（全局）[/green]")
    console.print(f"  [dim]{CLAUDE_JSON}[/dim]")


def _cleanup_legacy() -> None:
    """清理旧的 claude-manager / clm 命令和 MCP 配置。"""
    cleaned = []

    for name in ("clm", "claude-mgr"):
        path = LOCAL_BIN / name
        if path.exists():
            path.unlink()
            cleaned.append(f"~/.local/bin/{name}")

    if CLAUDE_JSON.exists():
        try:
            data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            if "claude-manager" in servers:
                del servers["claude-manager"]
                CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                cleaned.append("MCP: claude-manager")
        except (json.JSONDecodeError, OSError):
            pass

    if cleaned:
        console.print("  [dim]已清理旧配置:[/dim]")
        for item in cleaned:
            console.print(f"  [dim]  - {item}[/dim]")


def setup(
    skip_mcp: bool = typer.Option(False, "--no-mcp", help="跳过 MCP 注册"),
    skip_bin: bool = typer.Option(False, "--no-bin", help="跳过安装 dock 命令"),
    skip_cleanup: bool = typer.Option(False, "--no-cleanup", help="跳过清理旧配置"),
):
    """全局一键配置：安装 dock 命令 + 注册 MCP Server

    \b
    示例:
      dock setup              完整配置（命令 + MCP + 清理旧配置）
      dock setup --no-mcp     仅安装命令，不注册 MCP
      dock setup --no-bin     仅注册 MCP，不安装命令
    """
    console.print("[bold]Ocean Dock 全局配置[/bold]\n")
    bin_path = _resolve_bin()

    # 1. 安装 dock 全局命令
    if not skip_bin:
        console.print("[bold]1. 安装 dock 命令[/bold]")
        _install_dock_command(bin_path)
        console.print()

    # 2. 注册 MCP Server
    if not skip_mcp:
        console.print("[bold]2. 注册 MCP Server[/bold]")
        _register_mcp_global(bin_path)
        console.print()

    # 3. 清理旧配置
    if not skip_cleanup:
        console.print("[bold]3. 清理旧配置[/bold]")
        _cleanup_legacy()
        console.print()

    console.print("[bold green]配置完成![/bold green]")
    console.print("  [dim]重启 Claude Code 后生效，输入 /mcp 确认连接状态[/dim]")


def teardown(
    all: bool = typer.Option(False, "--all", help="同时卸载 dock 全局命令"),
):
    """一键卸载 MCP Server

    \b
    示例:
      dock teardown           仅移除 MCP Server 注册
      dock teardown --all     移除 MCP + 卸载 dock 命令
    """
    console.print("[bold]Ocean Dock 卸载[/bold]\n")

    # 1. 移除 MCP Server 注册
    console.print("[bold]1. 移除 MCP Server[/bold]")
    removed = False

    if CLAUDE_JSON.exists():
        try:
            data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            for name in ("ocean-dock", "claude-manager"):
                if name in servers:
                    del servers[name]
                    removed = True
                    console.print(f"  [green]已移除 MCP Server: {name}[/green]")
            if removed:
                CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            console.print(f"  [yellow]读取 {CLAUDE_JSON} 失败[/yellow]")

    if not removed:
        console.print("  [dim]未找到需要移除的 MCP 配置[/dim]")
    console.print()

    # 2. 可选：卸载 dock 命令
    if all:
        console.print("[bold]2. 卸载 dock 命令[/bold]")
        for name in ("dock", "clm", "claude-mgr"):
            path = LOCAL_BIN / name
            if path.exists():
                path.unlink()
                console.print(f"  [green]已删除 ~/.local/bin/{name}[/green]")
        console.print()

    console.print("[bold green]卸载完成![/bold green]")
    console.print("  [dim]重启 Claude Code 后生效[/dim]")
