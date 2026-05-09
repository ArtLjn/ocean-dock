"""dock init-harness — 一键初始化 Harness Engineering 基础设施"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ocean_dock.harness import init_harness

console = Console()


def harness_init(
    project_dir: str = typer.Argument("", help="目标项目路径（默认当前目录）"),
    project_name: str = typer.Option("", "-n", "--name", help="项目名称（默认用目录名）"),
    tech_stack: str = typer.Option("both", "-t", "--tech-stack", help="技术栈: python / ts / both"),
    backend_dir: str = typer.Option("backend", "--backend-dir", help="后端目录名"),
    frontend_dir: str = typer.Option("frontend", "--frontend-dir", help="前端目录名"),
):
    """一键初始化 Harness Engineering 基础设施

    自动生成 CLAUDE.md、docs/ 知识库、架构约束脚本、
    hooks（三要素格式）、4 个 agent、CI 管线（7道门）等完整基础设施。

    \b
    示例:
      dock init-harness                          当前目录，自动检测
      dock init-harness /path/to/project         指定目录
      dock init-harness -t python                纯 Python 项目
      dock init-harness -t ts -n my-app          纯前端项目，指定名称
    """
    target = Path(project_dir).resolve() if project_dir else Path.cwd()

    if tech_stack not in ("python", "ts", "both"):
        console.print(f"[red]无效技术栈: {tech_stack}，可选: python / ts / both[/red]")
        raise typer.Exit(1)

    name = project_name or target.name

    console.print("[bold]Harness Engineering 初始化[/bold]")
    console.print(f"  项目: [cyan]{name}[/cyan]")
    console.print(f"  路径: [dim]{target}[/dim]")
    console.print(f"  技术栈: [cyan]{tech_stack}[/cyan]")
    console.print()

    def log(msg: str):
        console.print(msg)

    result = init_harness(
        project_dir=target,
        project_name=name,
        tech_stack=tech_stack,
        backend_dir=backend_dir,
        frontend_dir=frontend_dir,
        on_log=log,
    )

    # 汇总
    console.print()
    table = Table(title="初始化结果", show_header=True)
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")
    table.add_row("新增文件", str(result["total_created"]))
    table.add_row("跳过文件", str(result["total_skipped"]))
    console.print(table)

    if result["total_created"] > 0:
        console.print("\n[bold green]下一步:[/bold green]")
        console.print("  1. 审阅 [cyan].claude/CLAUDE.md[/cyan] 中的硬性规则")
        console.print("  2. 审阅 [cyan]docs/architecture/boundaries.md[/cyan] 中的依赖方向")
        console.print("  3. 运行 [cyan]bash scripts/harness-check.sh[/cyan] 验证")
        console.print("  4. 提交代码，CI 管线自动生效")
