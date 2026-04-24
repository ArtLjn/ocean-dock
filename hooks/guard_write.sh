#!/bin/bash
# PreToolUse+Write/Edit hook: 拦截垃圾文件写入
# stdin: JSON {"tool_input": {"file_path": "...", ...}}
# exit 2 = 阻断写入

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")

[ -z "$FILE_PATH" ] && exit 0

# 文件名（不含路径）
FILENAME=$(basename "$FILE_PATH")

# --- 拦截规则 ---

# 1. 禁止写入编译缓存
if [[ "$FILE_PATH" == *__pycache__/* ]] || [[ "$FILENAME" == *.pyc ]] || [[ "$FILENAME" == *.pyo ]]; then
    echo "[GUARD_WRITE] 阻断: 禁止写入 Python 编译缓存文件: $FILE_PATH" >&2
    exit 2
fi

# 2. 禁止写入 .DS_Store
if [[ "$FILENAME" == .DS_Store ]]; then
    echo "[GUARD_WRITE] 阻断: 禁止写入 .DS_Store: $FILE_PATH" >&2
    exit 2
fi

# 3. 禁止直接修改 .git/ 内部文件
if [[ "$FILE_PATH" == */.git/* ]]; then
    echo "[GUARD_WRITE] 阻断: 禁止直接修改 .git/ 内部文件: $FILE_PATH" >&2
    exit 2
fi

# 4. 禁止写入 .egg-info
if [[ "$FILE_PATH" == *.egg-info/* ]] || [[ "$FILENAME" == *.egg-info ]]; then
    echo "[GUARD_WRITE] 阻断: 禁止写入 egg-info 目录: $FILE_PATH" >&2
    exit 2
fi

# 5. 在项目根目录创建临时测试脚本（检测常见模式）
# 提取父目录作为"疑似项目根"
DIR_PATH=$(dirname "$FILE_PATH")
if [[ "$FILENAME" == "test.py" || "$FILENAME" == "tmp.py" || "$FILENAME" == "debug.py" || "$FILENAME" == "scratch.py" ]]; then
    # 如果文件直接在某个目录下（不是 tests/ 子目录），则阻断
    BASE_DIR=$(basename "$DIR_PATH")
    if [[ "$BASE_DIR" != "tests" && "$BASE_DIR" != "test" && "$BASE_DIR" != "__pycache__" ]]; then
        echo "[GUARD_WRITE] 阻断: 禁止在非 tests 目录创建临时脚本 '$FILENAME'，请放在 tests/ 目录中" >&2
        exit 2
    fi
fi

exit 0
