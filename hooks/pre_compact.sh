#!/bin/bash
# PreCompact hook: 上下文压缩前保留关键信息摘要
# stdin: JSON {"session_id": "...", ...}

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))")

[ -z "$SESSION_ID" ] && exit 0

# 查找 ocean-dock 可执行文件
CLM_BIN="$(cd "$(dirname "$0")/../.." && pwd)/venv/bin/ocean-dock"
[ ! -x "$CLM_BIN" ] && CLM_BIN="$(which ocean-dock 2>/dev/null)"
[ -z "$CLM_BIN" ] && exit 0

# 生成当前 session 的摘要
SUMMARY=$("$CLM_BIN" summary "$SESSION_ID" 2>/dev/null)
[ -z "$SUMMARY" ] && exit 0

# 转义 JSON 特殊字符
ESCAPED=$(echo "$SUMMARY" | python3 -c "
import sys, json
print(json.dumps(sys.stdin.read().strip()))
")

# 通过 systemMessage 注入给 Claude，在压缩后保留关键信息
echo "{\"systemMessage\": \"以下是本次 session 被压缩前的工作摘要，请保留这些关键信息：\\n\\n$ESCAPED\"}"
