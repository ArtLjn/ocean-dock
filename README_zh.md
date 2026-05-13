**简体中文** | [English](./README.md)

<p align="center">
  <img src="./static/banner.png" alt="Ocean Dock Banner" width="800">
</p>

<p align="center">
  <strong>Ocean Dock</strong> — Claude Code 的会话管理 & Harness Engineering 工具箱
</p>

<p align="center">
  <em>Claude Code / Ocean CLI 的配套工具箱 — 会话管理 · Harness Engineering · MCP Server · Hooks · Skills</em>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#功能特性">功能特性</a> ·
  <a href="#命令一览">命令一览</a> ·
  <a href="#架构设计">架构设计</a> ·
  <a href="#配置说明">配置说明</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/License-MIT-2EA44F?style=flat-square" alt="MIT License"/>
  <img src="https://img.shields.io/badge/MCP-14_工具-FF6B6B?style=flat-square" alt="14 MCP Tools"/>
  <img src="https://img.shields.io/badge/Hooks-8_自动化-4ECDC4?style=flat-square" alt="8 Hooks"/>
  <img src="https://img.shields.io/badge/Harness-22_文件-9B59B6?style=flat-square" alt="Harness Engineering"/>
</p>

---

## 功能特性

- **会话管理** — 浏览、搜索、恢复、导出 Claude Code / Ocean CLI 的会话历史
- **Harness Engineering** — 一键初始化生成 22 个文件：CLAUDE.md、docs/ 知识库、架构约束、hooks、agents、rules、CI 流水线（7 道关卡）
- **MCP Server** — 14 个工具 + 3 个资源 + 2 个提示词，AI 可直接查询会话、初始化 Harness、同步文档
- **Hooks 系统** — 8 个自动化 hook（安全守卫、lint 检查、交接摘要、通知）
- **Skills 系统** — 4 个内置 skill（代码审查、工作日报、项目导航、会话交接）
- **项目模板** — Git hooks + .gitignore + 一键初始化
- **零依赖 API** — 纯本地读取 `~/.claude/` 数据，无需 API Key

## 快速开始

```bash
# 克隆并安装
git clone git@github.com:ArtLjn/ocean-dock.git
cd ocean-dock
pip install -e .

# 一键全局配置（安装 dock 命令 + 注册 MCP Server + 清理旧版）
dock setup

# 初始化当前项目（MCP + Skills + Hooks + Git）
dock init

# 列出所有项目
dock list

# 查看会话详情
dock show <session-id>

# 恢复会话
dock resume <session-id>
dock resume <session-id> --fork    # fork 模式

# 导出会话记录
dock export -f md -o sessions.md
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `dock setup` | 全局一键配置（命令 + MCP + 清理旧版） |
| `dock teardown` | 移除 MCP Server 注册（`--all` 同时卸载 dock 命令） |
| `dock init` | 项目级配置（MCP + Skills + Hooks + Git） |
| `dock list [PROJECT]` | 列出项目 / 展开项目下的会话 |
| `dock show <ID>` | 查看会话详情（对话时间线 + 文件变更） |
| `dock resume <ID>` | 恢复会话（支持 `--fork` 和 `--summary-only`） |
| `dock summary <ID>` | 生成交接上下文摘要 |
| `dock export` | 导出为 Markdown / JSON |
| `dock serve` | 启动 MCP Server（stdio / SSE 模式） |
| `dock config` | 查看或修改配置 |
| `dock switch` | 多 API Profile 管理 |

> 快捷别名：`dock` = `ocean-dock`

### `dock init` 选项

```bash
dock init                           # 完整配置（MCP + Skills + Hooks + Git）
dock init -s local                  # 仅本地项目作用域
dock init /path/to/project          # 指定目标目录
```

## 架构设计

```
ocean-dock/
├── src/ocean_dock/          # 主包
│   ├── cli.py               # CLI 入口
│   ├── models.py            # 数据模型
│   ├── session_store.py     # 会话数据层
│   ├── commands/            # CLI 子命令
│   │   └── init.py          # 一键初始化（ocean-dock + Harness）
│   ├── harness/             # Harness Engineering 生成器
│   │   └── generator.py     # 22 文件模板引擎
│   └── mcp/                 # MCP Server
│       ├── server.py        # FastMCP 实例
│       ├── tools.py         # 14 个工具（12 会话 + init_harness + sync_docs）
│       ├── resources.py     # 3 个资源
│       └── prompts.py       # 2 个提示词
├── hooks/                   # 8 个自动化 hook 脚本
├── skills/                  # 4 个 Skill 定义
├── templates/               # 项目模板（Git Hooks + .gitignore）
└── static/                  # Banner 和资源文件
```

### `dock init` 生成的项目结构

```
.claude/
├── CLAUDE.md              ← 地图模式入口（80 行，"想做什么 → 去哪里看"）
├── settings.json          ← 权限 + hooks + rules + agents
├── hooks/
│   ├── pre_tool_use.json  ← 危险命令拦截（三要素格式：❌+✅+📖）
│   └── post_tool_use.json ← 自动格式化 + 文档同步触发
├── rules/                 ← 按文件类型自动注入（python-style/frontend-style/security/docs-sync）
└── agents/                ← 4 个专业 agent（架构师→编码者→审查者→清理者）

docs/                      ← 结构化知识库
├── architecture/          ← 系统概览 + 依赖边界
├── conventions/           ← 编码规范索引
├── design/TEMPLATE.md     ← 功能设计模板（含状态追踪）
└── plans/current-sprint.md

scripts/                   ← 验证脚本
├── check-layer-deps.sh    ← 分层依赖 + 文件大小 + TODO 检查
├── check-doc-freshness.sh ← 文档新鲜度（默认 60 天阈值）
├── agent-verify.sh        ← Git Worktree 隔离验证
└── harness-check.sh       ← Harness 全量检查入口（7 道关卡）

.github/workflows/
└── harness-checks.yml     ← CI 流水线（类型检查 + lint + 测试 + 覆盖率 + 架构 + 大小 + 文档新鲜度）
```

### MCP 工具（14 个）

| 工具 | 说明 |
|------|------|
| `list_sessions` | 列出会话（可按项目过滤） |
| `show_session` | 查看会话详情 |
| `get_session_summary` | 生成交接上下文摘要 |
| `search_sessions` | 按关键字搜索会话 |
| `get_session_changes` | 获取文件变更（新建/修改/读取） |
| `get_session_requests` | 获取用户请求记录（去重） |
| `get_session_todos` | 获取 TodoWrite 任务进度快照 |
| `get_session_errors` | 获取错误和问题 |
| `get_session_decisions` | 获取关键决策 |
| `get_session_conversation` | 获取对话内容 |
| `list_projects` | 列出所有项目 |
| `git_commit` | 自动检测变更并提交 |
| **`init_harness`** | 一键初始化 Harness Engineering（22 个文件） |
| **`sync_docs`** | 扫描代码变更，生成文档同步待办清单 |

### Hooks（8 个）

| Hook | 事件 | 说明 |
|------|------|------|
| `notify.sh` | 通知 | macOS 声音提醒 |
| `session_start.sh` | SessionStart | 注入历史会话摘要 |
| `guard_bash.sh` | PreToolUse(Bash) | 拦截危险命令 |
| `guard_write.sh` | PreToolUse(Write/Edit) | 拦截垃圾文件写入 |
| `auto_check.sh` | PostToolUse(Edit/Write) | 文件修改后自动 lint |
| `pre_compact.sh` | PreCompact | 压缩前保留关键信息 |
| `stop.sh` | Stop | 保存交接摘要 |
| `cleanup_stop.sh` | Stop | 自动清理垃圾文件 |

## 配置说明

### 全局配置（推荐）

```bash
dock setup
```

此命令自动完成三件事：

1. **安装 `dock` 命令** — 写入 `~/.local/bin/dock`，全局可用
2. **注册 MCP Server** — 写入 `~/.claude.json`，Claude Code 启动时自动连接
3. **清理旧版** — 移除旧的 `clm`/`claude-mgr` 命令和 MCP 条目

```bash
dock setup --no-mcp      # 仅安装命令，跳过 MCP
dock setup --no-bin      # 仅注册 MCP，跳过命令
dock setup --no-cleanup  # 跳过旧版清理
```

### 卸载

```bash
dock teardown           # 仅移除 MCP Server
dock teardown --all     # 移除 MCP + 卸载 dock 命令
```

### 项目级配置

```bash
dock init               # 完整配置（MCP + Skills + Hooks + Git）
dock init -s local      # 仅本地项目作用域
```

### 手动注册 MCP

添加到 `~/.claude.json`（全局）或项目 `.claude/settings.json`：

```json
{
  "mcpServers": {
    "ocean-dock": {
      "type": "stdio",
      "command": "ocean-dock",
      "args": ["serve"]
    }
  }
}
```

如果不在 PATH 中，使用绝对路径：

```json
"command": "/path/to/ocean-dock/venv/bin/ocean-dock"
```

### 验证连接

重启 Claude Code，输入 `/mcp` 检查 `ocean-dock` 是否已连接。连接成功后，AI 可直接调用 14 个 MCP 工具：

```
> 查看最近的会话
> 搜索关于"重构"的历史对话
> 从上一个会话生成交接文档
> 为这个项目初始化 Harness Engineering
> 检查代码变更后哪些文档需要同步
```

## 搭配 Ocean CLI 使用

Ocean Dock 是 [Ocean CLI](https://github.com/ArtLjn/ocean-cc-cli) 的配套工具，也可以独立配合原生 Claude Code 使用。

```
Ocean CLI（宿主）                Ocean Dock（配套）
├── 多模型支持                   ├── 会话管理
├── Auto Mode                   ├── Harness Engineering（22 文件生成器）
├── 双层记忆                     ├── MCP Server（14 个工具）
├── 多模型协作                   ├── Hooks 自动化
├── Skill 系统                   ├── Skills 系统
└── 频道 IM 集成                 └── 项目模板
```

## 关键词

`claude-code` `mcp-server` `session-manager` `harness-engineering` `developer-tools` `cli` `hooks` `skills` `python` `anthropic` `ai-assistant` `productivity` `automation` `code-review` `developer-experience` `ocean-cli`

`会话管理` `MCP工具` `Harness工程` `开发自动化` `Claude CLI` `AI编程助手`

## 许可证

MIT
