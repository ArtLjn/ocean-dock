"""工具函数"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from rich.console import Console

CLAUDE_HOME = Path.home() / ".claude"
SESSIONS_DIR = CLAUDE_HOME / "sessions"
PROJECTS_DIR = CLAUDE_HOME / "projects"
CLAUDE_MGR_CONFIG = CLAUDE_HOME / "ocean-dock.json"

# 备份文件保留数量上限
_MAX_BACKUPS = 3


def safe_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """安全写入文件：写入前自动备份原文件，写入失败时自动回滚。

    备份规则：
    - 仅在目标文件已存在时备份
    - 最多保留 _MAX_BACKUPS 个备份（.bak → .bak.1 → .bak.2 → ...）
    - 写入采用先写临时文件再原子替换，避免写入中断导致文件损坏
    """
    if path.exists():
        # 滚动备份：.bak.2 → 删除, .bak.1 → .bak.2, .bak → .bak.1
        for i in range(_MAX_BACKUPS, 0, -1):
            older = path.parent / f"{path.name}.bak.{i}"
            newer = path.parent / f"{path.name}.bak.{i - 1}" if i > 1 else path.parent / f"{path.name}.bak"
            if newer.exists():
                shutil.copy2(newer, older)
        shutil.copy2(path, path.parent / f"{path.name}.bak")

    # 先写入临时文件，再原子替换
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding=encoding)
        tmp_path.replace(path)
    except BaseException:
        # 写入失败，清理临时文件
        tmp_path.unlink(missing_ok=True)
        raise


def decode_project_path(encoded: str) -> str:
    """将编码的项目路径解码为实际路径。

    Claude Code 将路径中的 "/" 替换为 "-"，但目录名中的 "-"
    也保持为 "-"，导致编码存在歧义。通过文件系统检查来消歧。

    例: -Users-ljn-Documents-demo-python-rag → /Users/ljn/Documents/demo/python-rag
    """
    if not encoded.startswith("-"):
        return encoded

    segments = encoded[1:].split("-")
    path_parts: list[str] = []
    i = 0

    while i < len(segments):
        found = False
        for end in range(i + 1, len(segments) + 1):
            combined = "-".join(segments[i:end])
            candidate = Path("/" + "/".join(path_parts + [combined]))
            if candidate.is_dir():
                path_parts.append(combined)
                i = end
                found = True
                break

        if not found:
            # 目录可能已删除，将剩余部分作为最后一个组件
            path_parts.append("-".join(segments[i:]))
            break

    return "/" + "/".join(path_parts)


def encode_project_path(path: str) -> str:
    """将实际路径编码为 Claude Code 的项目目录名。

    Claude Code 的编码规则：将所有非字母数字字符替换为 '-'。
    例如: /Users/ljn/.claude → -Users-ljn--claude
          skill_engine → skill-engine
          智能家居 → -----
    """
    import re
    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def parse_timestamp(ts: str | int | float) -> str:
    """将时间戳或 ISO 字符串统一格式化为可读时间。"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return str(ts)


def extract_text_from_message(msg: dict) -> str:
    """从 Claude 消息的 content 字段中提取纯文本。"""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return ""


def extract_file_paths(text: str) -> list[str]:
    """从文本中提取文件路径。"""
    # 匹配常见路径格式: /path/to/file.ext 或 ./relative/path
    pattern = r"(?:^|[\s(`'\"])((?:/[\w./\-]+|\.\/[\w./\-]+)\.\w+)"
    matches = re.findall(pattern, text)
    return list(set(matches))


def find_project_dir(session_id: str) -> Path | None:
    """根据 session_id 查找对应的项目 JSONL 文件。"""
    if not PROJECTS_DIR.exists():
        return None
    for proj_dir in PROJECTS_DIR.iterdir():
        if proj_dir.is_dir():
            jsonl = proj_dir / f"{session_id}.jsonl"
            if jsonl.exists():
                return proj_dir
    return None


def short_path(fp: str, cwd: str = "") -> str:
    """将文件路径缩短为相对路径或 ~ 路径。"""
    if cwd and fp.startswith(cwd + "/"):
        return fp[len(cwd) + 1:]
    home = str(Path.home()) + "/"
    if fp.startswith(home):
        return "~/" + fp[len(home):]
    return fp


def truncate(text: str, max_len: int = 50, suffix: str = "...") -> str:
    """截断文本。"""
    # 清理 IDE 标签
    text = re.sub(r"<[^>]+>", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def load_config() -> dict:
    """加载 ocean-dock 配置文件，不存在时返回默认配置。"""
    default_config = {
        "cli_command": "claude"  # 默认使用的 Claude CLI 命令名称
    }

    if not CLAUDE_MGR_CONFIG.exists():
        return default_config

    try:
        data = json.loads(CLAUDE_MGR_CONFIG.read_text(encoding="utf-8"))
        # 合并默认配置，确保所有键存在
        for key, value in default_config.items():
            data.setdefault(key, value)
        return data
    except (json.JSONDecodeError, OSError):
        console = Console()
        console.print(f"[yellow]警告: {CLAUDE_MGR_CONFIG} 格式异常，使用默认配置[/yellow]")
        return default_config


def save_config(config: dict) -> None:
    """保存配置到文件。"""
    safe_write(CLAUDE_MGR_CONFIG, json.dumps(config, indent=2, ensure_ascii=False) + "\n")
