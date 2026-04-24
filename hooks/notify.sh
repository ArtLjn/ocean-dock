#!/bin/bash
# Notification hook: Claude 需要你注意时播放声音
# 参数: $1 = matcher (permission_prompt / idle_prompt)

case "$1" in
  permission_prompt) afplay /System/Library/Sounds/Ping.aiff 2>/dev/null ;;
  idle_prompt)      afplay /System/Library/Sounds/Blow.aiff 2>/dev/null ;;
esac
