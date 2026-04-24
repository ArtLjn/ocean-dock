"""Ocean CLI 配套工具 — Session 管理 · MCP Server · Hooks · Skills"""

from __future__ import annotations

import os
import signal

import typer
from rich.console import Console

from ocean_dock.utils import CLAUDE_HOME, load_config, save_config
from ocean_dock.commands import export, init, list as list_cmd, resume, setup, show, summary, switch

app = typer.Typer(
    name="ocean-dock",
    help="Ocean CLI 配套工具",
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

SERVE_PID_FILE = CLAUDE_HOME / "serve.pid"


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Ocean CLI 配套工具（默认显示 session 列表）"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_cmd.list_sessions)


app.command("list")(list_cmd.list_sessions)
app.command("show")(show.show)
app.command("resume")(resume.resume)
app.command("export")(export.export)
app.command("summary")(summary.summary)
app.command("init")(init.init)
app.command("setup")(setup.setup)
app.command("teardown")(setup.teardown)
app.add_typer(switch.switch_app)


@app.command("config")
def config(
    key: str = typer.Argument(help="配置项名称（留空查看所有配置）", default=""),
    value: str = typer.Argument(help="配置项值（留空查看配置项当前值）", default=""),
):
    """查看或修改 ocean-dock 配置

    \b
    示例:
      dock config                    查看所有配置
      dock config cli_command        查看 cli_command 当前值
      dock config cli_command ocean  设置 cli_command 为 ocean
    """
    config = load_config()

    if not key:
        # 显示所有配置
        from rich.table import Table
        table = Table(title="Ocean Dock 配置")
        table.add_column("配置项", style="cyan")
        table.add_column("值")
        table.add_column("说明")

        table.add_row("cli_command", config["cli_command"], "Claude CLI 命令名称")

        console.print(table)
        console.print(f"\n配置文件路径: [dim]{CLAUDE_HOME / 'ocean-dock.json'}[/dim]")
        return

    if key not in config:
        console.print(f"[red]未知配置项: {key}[/red]")
        console.print(f"[dim]支持的配置项: {', '.join(config.keys())}[/dim]")
        raise typer.Exit(1)

    if not value:
        # 查看单个配置项
        console.print(f"{key} = {config[key]}")
        return

    # 设置配置项
    config[key] = value
    save_config(config)
    console.print(f"[green]已设置 {key} = {value}[/green]")


@app.command()
def serve(
    stop: bool = typer.Option(False, "-s", "--stop", help="停止后台 MCP Server"),
    background: bool = typer.Option(False, "-b", "--background", help="后台运行（SSE 模式）"),
    host: str = typer.Option("127.0.0.1", help="SSE 模式监听地址"),
    port: int = typer.Option(8765, "-p", "--port", help="SSE 模式监听端口"),
):
    """启动 MCP Server

    \b
    示例:
      ocean-dock serve              stdio 模式（供 Claude Code 自动拉起）
      ocean-dock serve -b           后台启动 SSE 服务
      ocean-dock serve -b -p 9000  指定端口后台启动
      ocean-dock serve -s           停止后台服务
    """
    import sys

    if stop:
        if not SERVE_PID_FILE.exists():
            console.print("[yellow]没有找到运行中的后台服务[/yellow]")
            raise typer.Exit(1)

        pid = int(SERVE_PID_FILE.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            SERVE_PID_FILE.unlink()
            console.print(f"[green]已停止后台 MCP Server (PID: {pid})[/green]")
        except ProcessLookupError:
            SERVE_PID_FILE.unlink()
            console.print(f"[yellow]PID {pid} 已不存在，已清理记录[/yellow]")
        except PermissionError:
            console.print(f"[red]无权限停止 PID {pid}[/red]")
            raise typer.Exit(1)
        return

    if background:
        # SSE 模式后台运行
        from mcp.server.fastmcp import FastMCP
        from ocean_dock.mcp import register_tools

        mcp = FastMCP("ocean-dock", host=host, port=port)
        register_tools(mcp)

        pid = os.fork()
        if pid > 0:
            # 父进程：记录 PID 并退出
            SERVE_PID_FILE.write_text(str(pid))
            console.print(f"[green]MCP Server 已后台启动 (sse://{host}:{port}, PID: {pid})[/green]")
            return

        # 子进程：脱离终端
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, sys.stdin.fileno())
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())

        mcp.run(transport="sse")
    else:
        # stdio 模式：Claude Code 的 MCP 客户端会在消息之间发送空行，
        # MCP SDK 的 stdio 传输会将空行当作 JSON 解析导致报错，
        # 因此 patch readline 跳过空行。
        _original_readline = sys.stdin.buffer.readline

        def _filtered_readline():
            while True:
                line = _original_readline()
                if not line or line.strip():
                    return line

        sys.stdin.buffer.readline = _filtered_readline
        print("ocean-dock MCP Server 启动 (stdio)", file=sys.stderr)
        sys.stderr.flush()

        from ocean_dock.mcp import mcp
        mcp.run(transport="stdio")

if __name__ == "__main__":
    app()
