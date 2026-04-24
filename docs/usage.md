# claude-mgr 使用指南：MCP + Hooks + Skills 全栈集成

## 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      Claude Code (你的 AI 助手)                    │
│                                                                  │
│  用户说"列出最近的 session"                                         │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────┐    ┌───────────┐    ┌───────────────────────┐      │
│  │  Skill    │───▶│ MCP Tool  │───▶│ claude-mgr serve       │      │
│  │ (触发器)  │    │ (调用)    │    │ (stdio 进程)           │      │
│  └──────────┘    └───────────┘    └───────────────────────┘      │
│       │                              │                          │
│       │         ┌──────────┐         │                          │
│       └────────▶│  Hook    │◀────────┘                          │
│                 │ (自动化)  │                                    │
│                 └──────────┘                                    │
└──────────────────────────────────────────────────────────────────┘
```

三者分工：

| 组件 | 角色 | 类比 |
|------|------|------|
| **MCP Server** | 提供数据能力（11 个 Tool + 3 个 Resource + 2 个 Prompt） | 餐厅后厨，负责做菜 |
| **Skill** | 定义触发条件和处理流程（4 个内置 Skill） | 菜单，告诉 Claude 什么时候点什么菜 |
| **Hook** | 在特定事件后自动执行命令（6 个 Hook） | 服务员，菜做好了自动端上来 |

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/your-username/claude-manager.git
cd claude-manager
pip install -e .
```

**依赖：**

- Python >= 3.10
- typer — CLI 框架
- rich — 终端美化
- jsonlines — JSONL 解析
- mcp — MCP 协议支持

### 2. 一键配置

在任意项目中执行：

```bash
cd /your/project
claude-mgr init              # 默认 user 级别注册 MCP
claude-mgr init -s local     # 项目级注册 MCP
```

这条命令会做三件事：

1. **注册 MCP Server** — `claude mcp add claude-manager -- claude-mgr serve`
2. **复制 Skill 文件** — 将 4 个 skill 复制到 `.claude/skills/`
3. **写入 Hook 配置** — 将 6 个 hook 写入 `.claude/settings.json`

生成的目录结构：

```
your-project/
└── .claude/
    ├── settings.json              ← MCP Server + 6 个 Hook 配置
    └── skills/
        ├── session-handoff.md     ← 会话交接 skill
        ├── daily-report.md        ← 日报生成 skill
        ├── code-review.md         ← 代码审查 skill
        └── project-nav.md         ← 项目导航 skill
```

### 3. 重启 Claude Code

配置写入后需要**重启 Claude Code** 才能生效。在该项目的 Claude 中输入 `/mcp` 确认看到 `claude-manager` 服务状态为 connected。

---

## MCP Server：Claude 的"千里眼"

MCP Server 让 Claude 能**直接查询你的历史 session**，而不需要你手动复制粘贴。

### 工作原理

当你执行 `claude-mgr init` 后，Claude Code 启动时会自动拉起一个 `claude-mgr serve` 子进程。Claude 和这个进程通过 stdin/stdout 通信，可以随时调用工具、读取资源、使用 Prompt 模板。

### 11 个 MCP Tools

#### 基础查询（4 个）

| 工具名 | 参数 | 功能 | 典型用法 |
|--------|------|------|----------|
| `list_sessions` | `project=""`, `limit=20` | 列出 session，支持按项目过滤 | "列出最近的 session"、"看看这个项目的历史会话" |
| `show_session` | `session_id` | 查看完整详情（用户消息列表） | "显示 session abc123 的内容" |
| `get_session_summary` | `session_id` | 生成上下文交接摘要（Markdown） | "帮我恢复上次的工作"、"生成交接报告" |
| `search_sessions` | `keyword` | 按关键字搜索（匹配 ID 或消息内容） | "搜一下有没有讨论过认证的会话" |

#### 细粒度查询（7 个）

| 工具名 | 参数 | 返回内容 | 典型用法 |
|--------|------|----------|----------|
| `get_session_changes` | `session_id` | 新建/修改/读取的文件列表 | "这个 session 改了哪些文件" |
| `get_session_requests` | `session_id` | 去重后的用户请求列表 | "列出这个 session 的所有需求" |
| `get_session_todos` | `session_id` | TodoWrite 任务进度快照 | "看看任务完成进度" |
| `get_session_errors` | `session_id` | 遇到的错误和问题 | "这个 session 出了什么问题" |
| `get_session_decisions` | `session_id` | 从 thinking 提取的关键决策 | "当时做了哪些技术决策" |
| `get_session_conversation` | `session_id`, `role="all"`, `limit=50` | 对话内容（按角色过滤） | "看看用户说了什么"、"只看助手回复" |
| `list_projects` | 无 | 所有项目及 session 统计 | "有哪些项目"、"项目概览" |

> 所有 `session_id` 参数都支持前缀匹配，不需要输入完整 ID。

### 3 个 MCP Resources

| URI | 类型 | 内容 |
|-----|------|------|
| `claude-manager://sessions` | 静态 | 所有 session 列表（JSON） |
| `claude-manager://session/{session_id}/work-summary` | 模板 | 指定 session 的原始工作摘要（JSON） |
| `claude-manager://session/{session_id}/messages` | 模板 | 指定 session 的对话流（JSON） |

Resource 提供原始 JSON 数据，适合需要结构化处理数据的场景（对比 Tool 返回的 Markdown 格式）。

### 2 个 MCP Prompts

| Prompt | 参数 | 用途 |
|--------|------|------|
| `session_handoff` | `session_id` | 生成交接班 prompt，引导 Claude 快速衔接上一个 session 的工作 |
| `session_compare` | `session_id_a`, `session_id_b` | 对比两个 session，分析文件交集/差集和需求关联 |

### 使用示例

配置好后，你可以在 Claude 中直接用自然语言：

```
你: 列出最近 5 个 session
→ Claude 调用 list_sessions(limit=5)

你: 搜索包含"重构"的 session
→ Claude 调用 search_sessions(keyword="重构")

你: 看看 session 6989b 做了什么
→ Claude 调用 show_session(session_id="6989b")

你: 这个 session 改了哪些文件？
→ Claude 调用 get_session_changes(session_id="6989b")

你: 列出这个 session 的所有用户需求
→ Claude 调用 get_session_requests(session_id="6989b")

你: 有哪些项目？
→ Claude 调用 list_projects()

你: 对比 session A 和 session B 的差异
→ Claude 调用 session_compare prompt
```

---

## Skills：Claude 的"经验手册"

Skill 定义了 Claude 在特定场景下的处理流程。`claude-mgr init` 会复制 4 个内置 Skill 到 `.claude/skills/`。

### 1. session-handoff — 会话交接

**触发词**：粘贴 session summary、"帮我交接上文"、"继续上次的工作"、"恢复上下文"、"resume"、"handoff"

**功能**：解析上一轮 session summary，生成结构化交接报告，包含工作概览、需求时间线、技术发现、待办事项。

**输出模板**：

```markdown
# Session 交接报告
> Session ID: [id] | 项目: [路径] | 分支: [分支]

## 一、工作概览
- 工作量: N 次编辑, N 次读取, N 次命令
- 核心改动文件: ...

## 二、需求时间线与状态
| # | 需求 | 状态 | 备注 |

## 三、关键技术发现
## 四、待办事项
## 五、建议的下一步
```

### 2. daily-report — 日报生成

**触发词**："日报"、"今天做了什么"、"工作汇报"、"daily report"

**功能**：汇总当天所有 Claude Code session，生成结构化工作日报。

**处理流程**：
1. 调用 `list_sessions` 筛选当天的 session
2. 调用 `get_session_changes` 获取文件变更
3. 调用 `get_session_requests` 获取用户需求
4. 合并去重，生成日报

### 3. code-review — 代码审查

**触发词**："审查代码"、"code review"、"代码检查"、"review"

**功能**：对指定 session 的代码变更进行全面审查，覆盖 5 个维度：

| 维度 | 检查内容 |
|------|----------|
| 安全性 | 注入、XSS、敏感信息泄露 |
| 代码质量 | 命名规范、复杂度、重复代码 |
| 性能 | N+1 查询、不必要的循环 |
| 错误处理 | 异常处理是否完善 |
| 最佳实践 | 是否遵循语言/框架最佳实践 |

### 4. project-nav — 项目导航

**触发词**："项目导航"、"了解项目"、"项目概览"、"project overview"

**功能**：快速了解项目结构和历史工作情况。

**输出内容**：
- 项目基本信息（路径、session 数、最近活跃时间）
- 目录结构（重点扫描 src/、lib/、app/ 等源码目录）
- 技术栈识别（通过 package.json、pyproject.toml 等）
- 历史工作记录（从 session 中提取）
- 关键文件说明
- 建议下一步

### 自定义 Skill

Skill 文件存放在 `.claude/skills/` 目录下，是标准的 Markdown 文件。你可以：

- 编辑现有 Skill 调整触发条件或输出格式
- 新增 `*.md` 文件创建自定义 Skill
- Skill 文件头部使用 YAML frontmatter 定义元信息：

```yaml
---
description: Skill 的简短描述
TRIGGER when: 触发条件描述
---
```

---

## Hooks：Claude 的"自动助理"

Hook 在特定事件发生时自动执行 shell 脚本，无需手动触发。`claude-mgr init` 会配置 6 个 Hook。

### 6 个 Hook 一览

| Hook | 事件 | Matcher | 功能 |
|------|------|---------|------|
| `notify.sh` | Notification | `permission_prompt` | Claude 需要权限时播放提示音 |
| `notify.sh` | Notification | `idle_prompt` | Claude 空闲等待时播放提示音 |
| `session_start.sh` | SessionStart | — | 新 session 启动时注入历史 session 列表 |
| `guard_bash.sh` | PreToolUse | `Bash` | 执行 bash 命令前拦截危险操作 |
| `auto_check.sh` | PostToolUse | `Edit\|Write\|MultiEdit` | 文件修改后自动运行 lint 检查 |
| `pre_compact.sh` | PreCompact | — | 上下文压缩前保留关键信息摘要 |
| `stop.sh` | Stop | — | Session 结束时自动保存交接摘要 |

### Hook 详解

#### notify.sh — 声音提醒

当 Claude 需要你注意时（权限请求、空闲等待），通过 macOS 系统音效提醒你：

- `permission_prompt` → 播放 Ping 提示音
- `idle_prompt` → 播放 Blow 提示音

#### session_start.sh — 智能恢复

新 session 启动时自动：
1. 找到当前项目对应的历史 session 目录
2. 列出最近 8 个 session（时间、消息数、首条用户消息预览）
3. 注入为 systemMessage，提示 Claude 询问你是否需要恢复某个 session

效果：每次打开 Claude Code，都会看到历史 session 列表，可以快速选择恢复。

#### guard_bash.sh — 危险命令拦截

在 Claude 执行 bash 命令前检查安全性。**安全放行**的命令包括：

- 只读命令：`ls`、`pwd`、`cat`、`head`、`tail`、`grep`、`find` 等
- 只读 git 命令：`git status`、`git diff`、`git log`、`git branch` 等

**阻断的危险操作**：

| 模式 | 说明 |
|------|------|
| `rm -rf /` | 删除根目录 |
| `rm -rf ~` | 删除 home 目录 |
| `DROP TABLE/DATABASE` | 删除数据库 |
| `git push --force` | 强制推送 |
| `mkfs` | 格式化文件系统 |
| `dd of=/dev/` | 写入块设备 |
| `shutdown/reboot` | 关机/重启 |
| `chmod 777 /` | 修改根权限 |

匹配到危险模式时返回 `exit 2`，Claude Code 会阻断命令执行。

#### auto_check.sh — 自动 lint

文件被修改后自动运行对应的检查工具：

| 文件类型 | 检查工具 |
|----------|----------|
| `.py` | `ruff check`（优先）或 `py_compile` |
| `.js/.jsx/.ts/.tsx` | `eslint`（需要 package.json） |
| `.go` | `go vet` |
| `.rs` | `cargo check` |

检查结果通过 stderr 反馈给 Claude，Claude 会自动修复发现的问题。

#### pre_compact.sh — 压缩保护

当 Claude Code 的上下文窗口接近上限需要压缩时：
1. 调用 `claude-mgr summary` 生成当前 session 摘要
2. 注入为 systemMessage，确保压缩后保留关键工作信息

效果：即使长对话被压缩，重要的工作上下文也不会丢失。

#### stop.sh — 自动交接

Session 结束时：
1. 从 stdin 读取 `session_id` 和 `cwd`
2. 调用 `claude-mgr summary` 生成交接摘要
3. 保存到 `$CWD/.claude/LAST_HANDOFF.md`

效果：每次 session 结束都自动保存交接文档，下次开新 session 时可以读取恢复。

### Hook 工作流程

```
SessionStart hook 触发
  → 注入历史 session 列表
  → 用户选择恢复某个 session
  → Claude 调用 get_session_summary 获取摘要
  → 开始工作...

工作中...
  → PreToolUse hook 拦截危险命令
  → PostToolUse hook 自动 lint 检查
  → PreCompact hook 保护上下文压缩

Session 结束...
  → Stop hook 自动保存交接摘要到 LAST_HANDOFF.md
```

---

## CLI 命令参考

`claude-mgr` 本身也是一个完整的 CLI 工具，可以独立于 Claude Code 使用：

```bash
# 列出所有项目（默认命令）
claude-mgr
claude-mgr list

# 展开某个项目的 sessions
claude-mgr list 3            # 按编号
claude-mgr list airQA        # 按路径模糊匹配
claude-mgr list airQA -n 50  # 显示 50 条

# 查看会话详情
claude-mgr show <session-id>        # 支持 session ID 前缀匹配
claude-mgr show -s "抢票"            # 按关键字搜索并展示

# 生成交接摘要
claude-mgr summary <session-id>           # 打印到终端
claude-mgr summary <session-id> -o ctx.md # 保存到文件
claude-mgr summary <session-id> -c        # 复制到剪贴板
claude-mgr summary <session-id> -r        # 生成并开新 session

# 恢复会话
claude-mgr resume <session-id>           # 直接恢复
claude-mgr resume <session-id> -f        # fork 模式

# 导出会话记录
claude-mgr export -f md -o overview.md              # Markdown
claude-mgr export -f json -o overview.json           # JSON
claude-mgr export -p airQA -n 10 -f md -o qa.md     # 指定项目和数量

# 一键配置
claude-mgr init                    # 当前目录，user 级别 MCP
claude-mgr init /path/to/project   # 指定目录
claude-mgr init -s local           # 项目级 MCP

# 启动 MCP Server（通常由 Claude Code 自动拉起）
claude-mgr serve                   # stdio 模式（默认）
claude-mgr serve -t sse -p 8765    # SSE 模式
```

---

## 典型使用场景

### 场景 1：跨 Session 继续工作

**问题**：昨天在 Claude 里做了一半的功能，今天开新 session，Claude 完全不知道昨天做了什么。

**解决方案**：

```
# 方式 A：自动恢复（推荐）
# 1. session_start hook 自动注入历史 session 列表
# 2. 你选择要恢复的 session
# 3. Claude 调用 get_session_summary 获取摘要

# 方式 B：手动查询
你: 列出昨天在这个项目的 session
你: 帮我看看 session 6989b 的摘要
你: 基于这个摘要，继续上次没完成的工作

# 方式 C：使用 session-handoff skill
你: 帮我恢复上次的工作
# Claude 触发 session-handoff，生成交接报告
```

### 场景 2：自动生成交接文档

**问题**：每次 session 结束都要手动跑命令生成交接报告。

**解决方案**：配置好 stop hook 后完全自动化。Session 结束时自动保存到 `.claude/LAST_HANDOFF.md`。

### 场景 3：团队协作交接

**问题**：同事 A 做完了一个功能，同事 B 需要接手。

**解决方案**：

```bash
# 同事 A 的 session 结束后
$ claude-mgr summary <session_id> -o handoff.md

# 把 handoff.md 发给同事 B
# 同事 B 在新 session 中：
你: [粘贴 handoff.md 的内容]
你: 帮我交接上文
```

### 场景 4：生成工作日报

**问题**：一天在多个项目上用 Claude 做了很多事，需要汇总汇报。

**解决方案**：

```
你: 日报
# Claude 触发 daily-report skill
# 自动汇总当天所有 session 的工作内容
```

### 场景 5：代码审查

**问题**：某个 session 改了很多代码，需要审查质量。

**解决方案**：

```
你: 审查代码 session 6989b
# Claude 触发 code-review skill
# 逐文件审查安全、质量、性能等维度
```

### 场景 6：快速了解新项目

**问题**：接手一个新项目，想快速了解结构和历史。

**解决方案**：

```
你: 项目导航
# Claude 触发 project-nav skill
# 扫描目录结构、识别技术栈、查看历史 session
```

### 场景 7：对比两个 Session

**问题**：想知道两个 session 是否改了相同的文件，需求是否有关联。

**解决方案**：

```
你: 对比 session abc123 和 def456
# Claude 调用 session_compare prompt
# 输出文件交集/差集、需求对比、关联分析
```

### 场景 8：回溯历史决策

**问题**："上周为什么选了 Redis 而不是 Memcached？"

**解决方案**：

```
你: 搜索包含"Redis"的 session
你: 看看 session abc123 的决策记录
→ Claude 调用 get_session_decisions
```

---

## 工作原理

Claude Code 将会话数据存储在本地：

```
~/.claude/
├── sessions/          # session 元数据（仅保留最近几条）
│   └── 70932.json
└── projects/          # 完整的对话记录
    ├── -Users-ljn-Documents-demo-claude-cli/
    │   ├── abc123.jsonl
    │   └── def456.jsonl
    └── -Users-ljn-Desktop-my-project/
        └── ...
```

claude-mgr 直接扫描 `projects/` 目录下所有 JSONL 文件，从中提取 session 元数据和消息内容，**无需连接任何远程服务**。

`extract_work_summary()` 从每个 JSONL 文件中提取 11 个字段：

| 字段 | 说明 |
|------|------|
| `files_modified` | 修改的文件及编辑次数 |
| `files_created` | 新建的文件 |
| `files_read` | 读取的文件 |
| `user_requests` | 用户请求记录 |
| `errors_or_issues` | 遇到的错误 |
| `decisions` | 关键决策 |
| `todo_snapshots` | 任务进度快照 |
| `git_branch` | Git 分支 |
| `tool_usage` | 工具使用统计 |
| `work_duration` | 工作时长 |
| `command_count` | 命令执行次数 |

这些数据通过 MCP Tools 按需暴露，也通过 Resources 提供原始 JSON 访问。

---

## 常见问题

### Q: MCP Server 连接失败怎么办？

1. 确认 `claude-mgr` 在 PATH 中：`which claude-mgr`
2. 确认 MCP 配置正确：检查 `.claude/settings.json` 中的 `mcpServers` 部分
3. 在 Claude 中输入 `/mcp` 查看连接状态
4. 手动测试 MCP Server：`echo '{}' | claude-mgr serve`（应该没有报错）

### Q: Hook 没有触发？

1. 确认 `.claude/settings.json` 中 hooks 配置正确
2. 重启 Claude Code 使配置生效
3. 检查 hook 脚本是否有执行权限：`ls -la claude_manager/hooks/*.sh`

### Q: Skill 没有被触发？

1. 确认 `.claude/skills/` 目录下有对应的 `.md` 文件
2. 尝试使用明确的触发词（如"帮我交接上文"、"日报"、"项目导航"）
3. 也可以直接粘贴 session summary 文本触发 session-handoff

### Q: 如何在多个项目中使用？

每个项目需要单独执行 `claude-mgr init`。也可以全局启用：

```bash
claude-mgr init -s user        # 全局注册 MCP Server
# 然后在每个项目中执行 init 复制 Skill 和 Hook
claude-mgr init -s local /path/to/project
```

### Q: 如何卸载/清理配置？

编辑 `.claude/settings.json`：
- 删除 `mcpServers` 中的 `claude-manager`
- 删除 `hooks` 中 claude-mgr 相关的条目
- 删除 `.claude/skills/` 中 claude-mgr 复制的文件

### Q: SSE 模式怎么用？

默认 stdio 模式供 Claude Code 自动拉起。SSE 模式适合后台运行、多客户端连接：

```bash
claude-mgr serve -t sse -p 8765
# 然后在 MCP 客户端配置中连接 sse://127.0.0.1:8765
```

### Q: 危险命令拦截误报怎么办？

编辑 `claude_manager/hooks/guard_bash.sh`，在 `SAFE_PATTERN` 中添加放行规则，或在危险检测部分调整正则匹配。
