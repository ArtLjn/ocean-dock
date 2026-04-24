#!/bin/bash
# SessionStart hook: 新 session 启动时注入项目最近 session 列表供用户选择
# stdin: JSON {"session_id": "...", "cwd": "..."}

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))")
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))")

# 查找 ocean-dock 可执行文件
CLM_BIN="$(cd "$(dirname "$0")/../.." && pwd)/venv/bin/ocean-dock"
[ ! -x "$CLM_BIN" ] && CLM_BIN="$(which ocean-dock 2>/dev/null)"
[ -z "$CLM_BIN" ] && exit 0

# 遍历所有项目目录，解码目录名后与 cwd 前缀匹配
PROJ_DIR=""
for dir in "$HOME/.claude/projects"/*/; do
    [ ! -d "$dir" ] && continue
    dir_name=$(basename "$dir")
    # 解码: -Users-ljn-Documents-demo → /Users/ljn/Documents/demo
    decoded=$(echo "$dir_name" | sed 's/^-//' | sed 's/-/\//g')
    # cwd 以 decoded 开头，或 decoded 以 cwd 开头（cwd 可能是子目录）
    if [[ "$CWD" == "$decoded"* || "$decoded" == "$CWD"* ]]; then
        PROJ_DIR="$dir"
        break
    fi
done
[ -z "$PROJ_DIR" ] && exit 0

# 用 python3 列出最近 8 个 session（排除当前 session），提取时间、消息数、首条用户消息预览
SESSION_LIST=$(python3 -c "
import json, os, glob, sys

proj_dir = '$PROJ_DIR'
session_id = '$SESSION_ID'
max_sessions = 8

files = sorted(glob.glob(os.path.join(proj_dir, '*.jsonl')), key=os.path.getmtime, reverse=True)

entries = []
for f in files:
    sid = os.path.splitext(os.path.basename(f))[0]
    if sid == session_id:
        continue
    try:
        mtime = os.path.getmtime(f)
        time_str = __import__('datetime').datetime.fromtimestamp(mtime).strftime('%m-%d %H:%M')
        lines = sum(1 for _ in open(f))
        # 尝试提取第一条用户消息作为预览
        preview = ''
        with open(f) as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                    if obj.get('type') == 'human' or obj.get('role') == 'user':
                        content = obj.get('message', {}).get('content', '') or obj.get('content', '')
                        if isinstance(content, list):
                            content = ' '.join(
                                c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') == 'text'
                            )
                        content = str(content).strip()
                        if content:
                            # 清理 IDE 标签，截断
                            import re
                            content = re.sub(r'<[^>]+>', '', content)
                            content = content[:80].strip()
                            if len(content) >= 80:
                                content += '...'
                            preview = content
                        break
                except:
                    pass
        entries.append(f'{sid[:8]}  {time_str}  {lines}条消息  {preview}')
    except:
        pass
    if len(entries) >= max_sessions:
        break

for i, e in enumerate(entries, 1):
    print(f'{i}. {e}')
" 2>/dev/null)

[ -z "$SESSION_LIST" ] && exit 0

# 转义为 JSON 字符串
ESCAPED=$(echo "$SESSION_LIST" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

# 构建 systemMessage
MSG="该项目有以下历史 session，请展示给用户并询问是否需要恢复某个 session 的上下文（支持多选）：\\n\\n$ESCAPED\\n\\n用户选择后，请使用 claude-manager MCP 工具的 get_session_summary 获取对应 session 的摘要并展示。"

# 检测架构记忆是否需要更新
ARCH_FLAG="$CWD/.claude/memory/.arch-stale"
if [ -f "$ARCH_FLAG" ]; then
    MSG="${MSG}\\n\\n[系统提示] 检测到项目结构发生了变化，请检查 .claude/memory/_project_context.md 并更新项目架构概览（目录结构、技术栈、核心模块等）。更新完成后直接修改文件即可，无需询问用户。"
    rm -f "$ARCH_FLAG"
fi

echo "{\"systemMessage\": \"$MSG\"}"
