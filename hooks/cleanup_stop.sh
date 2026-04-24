#!/bin/bash
# Stop hook: session 结束时自动清理垃圾文件
# stdin: JSON {"session_id": "...", "cwd": "...", ...}

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))")

[ -z "$CWD" ] && exit 0
[ ! -d "$CWD" ] && exit 0

CLEANED=0

# 清理 __pycache__ 目录
find "$CWD" -type d -name "__pycache__" 2>/dev/null | while read -r dir; do
    rm -rf "$dir"
    CLEANED=1
done

# 清理 .pyc / .pyo 文件
find "$CWD" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null && CLEANED=1

# 清理 .DS_Store
find "$CWD" -type f -name ".DS_Store" -delete 2>/dev/null && CLEANED=1

# 清理 .egg-info 目录
find "$CWD" -type d -name "*.egg-info" 2>/dev/null | while read -r dir; do
    rm -rf "$dir"
    CLEANED=1
done

# 清理 .ruff_cache
find "$CWD" -type d -name ".ruff_cache" 2>/dev/null | while read -r dir; do
    rm -rf "$dir"
    CLEANED=1
done

# 清理 .pytest_cache
find "$CWD" -type d -name ".pytest_cache" 2>/dev/null | while read -r dir; do
    rm -rf "$dir"
    CLEANED=1
done

# 清理根目录的临时测试文件
for f in "$CWD"/test.py "$CWD"/tmp.py "$CWD"/debug.py "$CWD"/scratch.py; do
    if [ -f "$f" ]; then
        rm -f "$f"
        CLEANED=1
    fi
done

if [ "$CLEANED" -eq 1 ]; then
    echo "[CLEANUP] session 结束，已自动清理垃圾文件" >&2
fi

exit 0
