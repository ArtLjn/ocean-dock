<p align="center">
  <img src="./static/banner.png" alt="Ocean Dock Banner" width="800">
</p>

<p align="center">
  <strong>Ocean CLI 配套工具 — Session 管理 · MCP Server · Hooks · Skills</strong>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#功能特性">功能</a> ·
  <a href="#命令一览">命令</a> ·
  <a href="#架构">架构</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"/>
</p>

---

## 功能特性

- **Session 管理** — 浏览、搜索、恢复、导出 Claude Code / Ocean CLI 会话记录
- **MCP Server** — 12 个 Tools + 3 个 Resources + 2 个 Prompts，AI 直接查询历史会话
- **Hooks 系统** — 8 个自动化 Hook（安全防护、代码检查、交接摘要、通知提醒）
- **Skills 系统** — 4 个内置 Skill（代码审查、日报生成、项目导航、会话交接）
- **项目模板** — Git Hooks + .gitignore + 一键初始化
- **零依赖 API** — 纯本地读取 `~/.claude/` 数据，不需要 API Key

## 快速开始

```bash
# 安装
pip install -e .

# 一键配置（注册 MCP + 复制 Skill + 写入 Hooks + Git 初始化）
ocean-dock init

# 查看所有项目
ocean-dock list

# 查看会话详情
ocean-dock show <session-id>

# 恢复会话
ocean-dock resume <session-id>
ocean-dock resume <session-id> --fork    # fork 模式

# 导出会话记录
ocean-dock export -f md -o sessions.md
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `ocean-dock list [PROJECT]` | 列出项目 / 展开项目下的 session |
| `ocean-dock show <ID>` | 查看会话详情（对话时间线 + 涉及文件） |
| `ocean-dock resume <ID>` | 恢复会话（支持 `--fork` 和 `--summary-only`） |
| `ocean-dock summary <ID>` | 生成交接上下文摘要 |
| `ocean-dock export` | 导出为 Markdown / JSON |
| `ocean-dock init` | 一键配置 MCP + Skill + Hooks + Git |
| `ocean-dock serve` | 启动 MCP Server（stdio / SSE 模式） |
| `ocean-dock config` | 查看或修改配置 |
| `ocean-dock switch` | 多 API Profile 管理 |

> 短命令别名：`dock` = `ocean-dock`

## 架构

```
ocean-dock/
├── src/ocean_dock/          # 主包
│   ├── cli.py               # CLI 入口
│   ├── models.py            # 数据模型
│   ├── session_store.py     # Session 数据读取层
│   ├── commands/            # CLI 子命令
│   └── mcp/                 # MCP Server
│       ├── server.py        # FastMCP 实例
│       ├── tools.py         # 12 个 Tools
│       ├── resources.py     # 3 个 Resources
│       └── prompts.py       # 2 个 Prompts
├── hooks/                   # 8 个自动化 Hook 脚本
├── skills/                  # 4 个 Skill 定义
├── templates/               # 项目模板（Git Hooks + .gitignore）
└── docs/                    # 文档
```

### MCP Tools（12 个）

| Tool | 功能 |
|------|------|
| `list_sessions` | 列出 session（支持按项目过滤） |
| `show_session` | 查看会话详情 |
| `get_session_summary` | 生成交接上下文摘要 |
| `search_sessions` | 按关键字搜索 session |
| `get_session_changes` | 获取文件变更（新建/修改/读取） |
| `get_session_requests` | 获取用户请求（去重后） |
| `get_session_todos` | 获取 TodoWrite 任务进度 |
| `get_session_errors` | 获取错误和问题 |
| `get_session_decisions` | 获取关键决策 |
| `get_session_conversation` | 获取对话内容 |
| `list_projects` | 列出所有项目 |
| `git_commit` | 自动提交 git 更改 |

### Hooks（8 个）

| Hook | 事件 | 功能 |
|------|------|------|
| `notify.sh` | Notification | macOS 声音提醒 |
| `session_start.sh` | SessionStart | 注入历史 session 摘要 |
| `guard_bash.sh` | PreToolUse(Bash) | 拦截危险命令 |
| `guard_write.sh` | PreToolUse(Write/Edit) | 阻断垃圾文件写入 |
| `auto_check.sh` | PostToolUse(Edit/Write) | 文件修改后自动 lint |
| `pre_compact.sh` | PreCompact | 压缩前保留关键信息 |
| `stop.sh` | Stop | 保存交接摘要 |
| `cleanup_stop.sh` | Stop | 自动清理垃圾文件 |

## 安装

**从源码安装：**

```bash
git clone git@github.com:ArtLjn/ocean-duck.git
cd ocean-duck
pip install -e .
```

**依赖：** Python >= 3.10

## 配置 MCP Server

Ocean Dock 通过 MCP 协议为 Claude Code / Ocean CLI 提供 session 管理能力。

### 方式一：一键配置（推荐）

```bash
ocean-dock init          # 全局注册（所有项目可用）
ocean-dock init -s local # 仅当前项目
```

该命令会自动完成：注册 MCP Server + 复制 Skill + 写入 Hooks + Git 初始化。

### 方式二：手动注册

在 `~/.claude.json`（全局）或项目 `.claude/settings.json` 中添加：

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

如果 `ocean-dock` 不在 PATH 中，使用绝对路径：

```json
{
  "mcpServers": {
    "ocean-dock": {
      "type": "stdio",
      "command": "/path/to/ocean-duck/venv/bin/ocean-dock",
      "args": ["serve"]
    }
  }
}
```

### 验证连接

重启 Claude Code 后，输入 `/mcp` 查看 `ocean-dock` 是否连接成功。连接后 AI 可直接调用 12 个 MCP Tools，例如：

```
> 帮我查看最近的 session
> 搜索关于 "重构" 的历史对话
> 生成上一次会话的交接文档
```

## 与 Ocean CLI 配合

Ocean Dock 是 [Ocean CLI](https://github.com/your-username/ocean-cli) 的配套工具，但也可以独立使用于原生 Claude Code 环境。

```
Ocean CLI (主程序)          Ocean Dock (配套工具)
├── 多模型接入              ├── Session 管理
├── Auto Mode               ├── MCP Server
├── 双层记忆系统            ├── Hooks 自动化
├── 多模型协作              ├── Skills 技能
├── 技能系统                └── 项目模板
└── Channel IM 集成
```

## License

MIT
