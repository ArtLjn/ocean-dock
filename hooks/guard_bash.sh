#!/bin/bash
# PreToolUse+Bash hook: 拦截危险 bash 命令
# stdin: JSON {"tool_input": {"command": "..."}}
# exit 2 = 阻断命令执行

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))")

[ -z "$CMD" ] && exit 0

# 提取命令主体（去掉管道、重定向等）
# 获取第一个命令（管道前的部分）
FIRST_CMD=$(echo "$CMD" | sed 's/|.*//' | sed 's/&&.*//' | sed 's/||.*//' | sed 's/;.*//' | xargs)

# 安全放行的命令模式（只读/无副作用）
SAFE_PATTERN='^(ls|pwd|echo|cat|head|tail|wc|which|whoami|uname|date|env|printenv|type|true|false|test|basename|dirname|realpath|readlink|file|stat|du|df|uptime|hostname|id|groups|ulimit|locale|set|export|declare|local|return|break|continue|alias|unalias|hash|builtin|command|shopt|compgen|complete|bind|help|logout|printf|seq|yes|tee|tr|cut|sort|uniq|grep|find|diff|patch|git (status|diff|log|branch|remote|tag|stash|show|rev-parse|config|symbolic-ref))'

if echo "$FIRST_CMD" | grep -qE "$SAFE_PATTERN"; then
    exit 0
fi

# 危险模式检测（匹配则 exit 2 阻断）
DANGEROUS=0

# 删除系统关键目录（只匹配直接删除整个目录的操作）
# 匹配: rm -rf /etc, rm -rf /usr, rm -rf /bin, rm -rf /sbin, rm -rf /var
echo "$CMD" | grep -qiE 'rm\s+(-[a-zA-Z]*[frR][a-zA-Z]*\s+)?/(etc|usr|bin|sbin|var|lib|boot|dev|proc|sys|root)(/\*|\s|$)' && {
    # 排除在这些目录下删除单个文件的情况，比如 rm /etc/hosts 是允许的
    if ! echo "$CMD" | grep -qiE 'rm\s+.*(/etc|/usr|/bin|/sbin|/var|/lib|/boot|/dev|/proc|/sys|/root)/[^/]+'; then
        echo "[GUARD] 危险: 检测到删除系统关键目录操作" >&2
        DANGEROUS=1
    fi
}

# 删除 home 目录（只匹配真正危险的操作）
# 匹配: rm -rf ~, rm -rf ~/*, rm ~, rm ~/*
echo "$CMD" | grep -qiE 'rm\s+(-[a-zA-Z]*[frR][a-zA-Z]*\s+)?(~(/\*)?\s*$)' && {
    echo "[GUARD] 危险: 检测到删除 home 目录操作" >&2
    DANGEROUS=1
}

# 删除数据库
echo "$CMD" | grep -qiE '(DROP\s+(TABLE|DATABASE|SCHEMA))' && {
    echo "[GUARD] 危险: 检测到 DROP TABLE/DATABASE 操作" >&2
    DANGEROUS=1
}

# 强制推送
echo "$CMD" | grep -qiE 'git\s+push\s+.*(-(-force|-f)\b)' && {
    echo "[GUARD] 危险: 检测到 git push --force 操作" >&2
    DANGEROUS=1
}

# 格式化文件系统
echo "$CMD" | grep -qiE '\bmkfs\b' && {
    echo "[GUARD] 危险: 检测到 mkfs 格式化操作" >&2
    DANGEROUS=1
}

# dd 写入块设备
echo "$CMD" | grep -qiE 'dd\b.*of=/dev/' && {
    echo "[GUARD] 危险: 检测到 dd 写入块设备操作" >&2
    DANGEROUS=1
}

# 关机/重启
echo "$CMD" | grep -qiE '\b(shutdown|reboot|halt|poweroff|init\s+[06])\b' && {
    echo "[GUARD] 危险: 检测到关机/重启操作" >&2
    DANGEROUS=1
}

# 直接写块设备
echo "$CMD" | grep -qiE '>\s*/dev/[sh]d[a-z]' && {
    echo "[GUARD] 危险: 检测到直接写块设备操作" >&2
    DANGEROUS=1
}

# chmod 777 / (修改根权限)
echo "$CMD" | grep -qiE 'chmod\s+(-R\s+)?777\s+/' && {
    echo "[GUARD] 危险: 检测到对根目录设置 777 权限" >&2
    DANGEROUS=1
}

if [ "$DANGEROUS" -eq 1 ]; then
    exit 2
fi

exit 0
