#!/bin/bash
# Stop hook: session 结束时自动保存交接摘要 + 检测项目结构变化
# stdin: JSON {"session_id": "...", "cwd": "...", ...}

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))")
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))")

[ -z "$SESSION_ID" ] && exit 0

# 查找 ocean-dock 可执行文件
CLM_BIN="$(cd "$(dirname "$0")/../.." && pwd)/venv/bin/ocean-dock"
[ ! -x "$CLM_BIN" ] && CLM_BIN="$(which ocean-dock 2>/dev/null)"
[ -z "$CLM_BIN" ] && exit 0

# 生成当前 session 的摘要
SUMMARY=$("$CLM_BIN" summary "$SESSION_ID" 2>/dev/null)
[ -z "$SUMMARY" ] && exit 0

# 保存到项目的 .claude/LAST_HANDOFF.md
HANDOFF_DIR=""
if [ -n "$CWD" ] && [ -d "$CWD" ]; then
    HANDOFF_DIR="$CWD/.claude"
fi
if [ -z "$HANDOFF_DIR" ]; then
    exit 0
fi

mkdir -p "$HANDOFF_DIR"
echo "$SUMMARY" > "$HANDOFF_DIR/LAST_HANDOFF.md"

# --- 检测项目结构变化，标记架构记忆需要更新 ---
MEMORY_DIR="$HANDOFF_DIR/memory"
ARCH_FLAG="$MEMORY_DIR/.arch-stale"
ARCH_HASH_FILE="$MEMORY_DIR/.arch-hash"

if [ -d "$CWD" ] && [ -d "$MEMORY_DIR" ]; then
    # 生成结构指纹：前 2 层目录 + 关键配置文件
    CURRENT_HASH=$(find "$CWD" -maxdepth 2 -type d \
        ! -path '*/node_modules*' ! -path '*/.git*' ! -path '*/venv*' \
        ! -path '*/__pycache__*' ! -path '*/dist*' ! -path '*/build*' \
        ! -path '*/.next*' ! -path '*/.claude*' \
        2>/dev/null | sort | md5)

    # 检查关键配置文件是否存在并加入指纹
    for f in package.json pyproject.toml Cargo.toml go.mod pom.xml build.gradle Makefile; do
        [ -f "$CWD/$f" ] && CURRENT_HASH="${CURRENT_HASH}:$f"
    done

    STORED_HASH=""
    [ -f "$ARCH_HASH_FILE" ] && STORED_HASH=$(cat "$ARCH_HASH_FILE")

    if [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
        echo "$CURRENT_HASH" > "$ARCH_HASH_FILE"
        touch "$ARCH_FLAG"
    fi
fi
