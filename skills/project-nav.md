---
description: 快速了解项目结构和历史工作
TRIGGER when: 用户说 "项目导航"、"了解项目"、"项目概览"、"project overview"
Base directory for this skill: claude_manager
---

# 项目导航

你是一位项目分析助手。请帮助用户快速了解当前项目的结构和历史工作情况。

## 执行步骤

1. 调用 `list_projects` 获取所有项目列表
2. 对当前项目（或用户指定的项目），调用 `list_sessions` 获取历史 session
3. 调用最近几个 session 的 `get_session_changes` 了解主要变更
4. 扫描项目目录结构（使用 Glob 和 Read 工具）

## 输出格式

```markdown
# 项目导航 — {项目名}

## 基本信息
- 路径: {项目路径}
- 历史 session 数: {数量}
- 最近活跃: {时间}

## 目录结构
{主要目录和文件的树形结构}

## 主要模块
- {模块名}: {简要说明}

## 最近工作记录
### {日期} — Session {id}
- {工作摘要}

## 关键文件
- {文件路径}: {用途说明}

## 建议下一步
- {基于项目状态的建议}
```

注意：
- 重点关注 src/、lib/、app/ 等源码目录
- 识别项目使用的技术栈（通过配置文件如 package.json、pyproject.toml 等）
- 总结历史 session 中用户最常操作的功能模块
