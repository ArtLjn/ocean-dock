#!/bin/bash
# PostToolUse+Edit/Write hook: 文件修改后自动运行格式化/lint
# stdin: JSON {"tool_input": {"file_path": "..."}}
# 不阻断，结果通过 stderr 反馈给 Claude

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")

[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0

# 文件行数检查（所有文件类型，阈值 1000 行）
FILE_LINES=$(wc -l < "$FILE_PATH")
if [ "$FILE_LINES" -gt 1000 ]; then
    echo "[AUTO-CHECK] 文件行数警告: $FILE_PATH 已有 ${FILE_LINES} 行，超过 1000 行上限，请考虑拆分模块" >&2
fi

# 获取文件所在目录
FILE_DIR=$(dirname "$FILE_PATH")
# 获取文件后缀
EXT="${FILE_PATH##*.}"

check_and_report() {
    local label="$1"
    local cmd="$2"
    local output
    output=$(cd "$FILE_DIR" && eval "$cmd" 2>&1)
    if [ $? -ne 0 ] && [ -n "$output" ]; then
        echo "[AUTO-CHECK] $label 检查结果:" >&2
        echo "$output" | head -30 >&2
        if [ "$(echo "$output" | wc -l)" -gt 30 ]; then
            echo "... (更多输出已截断)" >&2
        fi
    fi
}

case "$EXT" in
    py)
        if command -v ruff &>/dev/null; then
            check_and_report "ruff" "ruff check '$FILE_PATH'"
        else
            check_and_report "py_compile" "python3 -m py_compile '$FILE_PATH'"
        fi
        ;;
    js|jsx|ts|tsx)
        # 只在 package.json 存在时运行 eslint
        if [ -f "$FILE_DIR/package.json" ] || [ -f "$(cd "$FILE_DIR" && git rev-parse --show-toplevel 2>/dev/null)/package.json" ]; then
            if command -v npx &>/dev/null; then
                check_and_report "eslint" "npx eslint --no-warn-ignored '$FILE_PATH'"
            fi
        fi
        ;;
    go)
        if command -v go &>/dev/null; then
            check_and_report "go vet" "go vet './$(basename "$FILE_PATH" ".$EXT")...'"
        fi
        ;;
    rs)
        if command -v cargo &>/dev/null; then
            # cargo check 需要在项目根目录运行
            check_and_report "cargo check" "cargo check 2>&1"
        fi
        ;;
esac

exit 0
