<p align="center">
  <img src="./static/banner.png" alt="Ocean Dock Banner" width="800">
</p>

<p align="center">
  <strong>Ocean Dock</strong> — Session Manager & Harness Engineering Toolkit for Claude Code
</p>

<p align="center">
  <em>Claude Code / Ocean CLI 的配套工具箱 — 会话管理 · Harness Engineering · MCP Server · Hooks · Skills</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#features">Features</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#configuration">Configuration</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/License-MIT-2EA44F?style=flat-square" alt="MIT License"/>
  <img src="https://img.shields.io/badge/MCP-14_Tools-FF6B6B?style=flat-square" alt="14 MCP Tools"/>
  <img src="https://img.shields.io/badge/Hooks-8_Automations-4ECDC4?style=flat-square" alt="8 Hooks"/>
  <img src="https://img.shields.io/badge/Harness-22_Files-9B59B6?style=flat-square" alt="Harness Engineering"/>
</p>

---

## Features

- **Session Management** — Browse, search, resume, and export Claude Code / Ocean CLI session history
- **Harness Engineering** — One-click init generates 22 files: CLAUDE.md, docs/ knowledge base, architecture constraints, hooks, agents, rules, CI pipeline with 7 gates
- **MCP Server** — 14 Tools + 3 Resources + 2 Prompts, AI directly queries sessions, inits harness, and syncs docs
- **Hooks System** — 8 automation hooks (security guards, lint checks, handoff summaries, notifications)
- **Skills System** — 4 built-in skills (code review, daily report, project navigation, session handoff)
- **Project Templates** — Git hooks + .gitignore + one-click initialization
- **Zero-dependency API** — Pure local `~/.claude/` data reading, no API key required

## Quick Start

```bash
# Clone and install
git clone git@github.com:ArtLjn/ocean-duck.git
cd ocean-duck
pip install -e .

# One-click global setup (install dock command + register MCP Server + cleanup legacy)
dock setup

# Initialize current project (MCP + Skills + Hooks + Git + Harness Engineering)
dock init

# List all projects
dock list

# View session details
dock show <session-id>

# Resume a session
dock resume <session-id>
dock resume <session-id> --fork    # fork mode

# Export session records
dock export -f md -o sessions.md
```

## Commands

| Command | Description |
|---------|-------------|
| `dock setup` | Global one-click setup (command + MCP + cleanup) |
| `dock teardown` | Remove MCP Server registration (+ `--all` to uninstall dock) |
| `dock init` | Project-level setup (MCP + Skills + Hooks + Git + **Harness Engineering**) |
| `dock list [PROJECT]` | List projects / expand sessions under a project |
| `dock show <ID>` | View session details (conversation timeline + file changes) |
| `dock resume <ID>` | Resume session (supports `--fork` and `--summary-only`) |
| `dock summary <ID>` | Generate handoff context summary |
| `dock export` | Export as Markdown / JSON |
| `dock serve` | Start MCP Server (stdio / SSE mode) |
| `dock config` | View or modify configuration |
| `dock switch` | Multi API Profile management |

> Short alias: `dock` = `ocean-dock`

### `dock init` Options

```bash
dock init                           # Full setup with Harness (default)
dock init --no-harness              # Skip Harness Engineering, only ocean-dock setup
dock init -t python                 # Python-only project (no frontend rules)
dock init -t ts                     # TypeScript-only project (no Python rules)
dock init -t both                   # Full-stack project (default)
dock init --backend-dir app         # Custom backend directory name
dock init --frontend-dir web        # Custom frontend directory name
```

## Architecture

```
ocean-dock/
├── src/ocean_dock/          # Main package
│   ├── cli.py               # CLI entry point
│   ├── models.py            # Data models
│   ├── session_store.py     # Session data layer
│   ├── commands/            # CLI subcommands
│   │   └── init.py          # One-click init (ocean-dock + Harness)
│   ├── harness/             # Harness Engineering generator
│   │   └── generator.py     # 22-file template engine
│   └── mcp/                 # MCP Server
│       ├── server.py        # FastMCP instance
│       ├── tools.py         # 14 Tools (12 session + init_harness + sync_docs)
│       ├── resources.py     # 3 Resources
│       └── prompts.py       # 2 Prompts
├── hooks/                   # 8 automation hook scripts
├── skills/                  # 4 Skill definitions
├── templates/               # Project templates (Git Hooks + .gitignore)
└── static/                  # Banner & assets
```

### `dock init` Generated Structure

```
.claude/
├── CLAUDE.md              ← Map-mode entry (80 lines, "what to do → where to look")
├── settings.json          ← Permissions + hooks + rules + agents
├── hooks/
│   ├── pre_tool_use.json  ← Danger command blocking (3-element format: ❌+✅+📖)
│   └── post_tool_use.json ← Auto format + doc sync trigger
├── rules/                 ← Auto-injected by file type (python-style/frontend-style/security/docs-sync)
└── agents/                ← 4 specialized agents (architect→coder→reviewer→cleanup)

docs/                      ← Structured knowledge base
├── architecture/          ← System overview + dependency boundaries
├── conventions/           ← Coding standards index
├── design/TEMPLATE.md     ← Feature design template (with Status tracking)
└── plans/current-sprint.md

scripts/                   ← Verification scripts
├── check-layer-deps.sh    ← Layer dependency + file size + TODO check
├── check-doc-freshness.sh ← Document freshness (default 60-day threshold)
├── agent-verify.sh        ← Git Worktree isolated verification
└── harness-check.sh       ← Full harness check entry (7 gates)

.github/workflows/
└── harness-checks.yml     ← CI pipeline (type check + lint + test + coverage + arch + size + doc freshness)
```

### MCP Tools (14)

| Tool | Description |
|------|-------------|
| `list_sessions` | List sessions (filter by project) |
| `show_session` | View session details |
| `get_session_summary` | Generate handoff context summary |
| `search_sessions` | Search sessions by keyword |
| `get_session_changes` | Get file changes (create/modify/read) |
| `get_session_requests` | Get user requests (deduplicated) |
| `get_session_todos` | Get TodoWrite task progress |
| `get_session_errors` | Get errors and issues |
| `get_session_decisions` | Get key decisions |
| `get_session_conversation` | Get conversation content |
| `list_projects` | List all projects |
| `git_commit` | Auto-detect changes and commit |
| **`init_harness`** | One-click Harness Engineering init (22 files) |
| **`sync_docs`** | Scan code changes, generate doc sync todo list |

### Hooks (8)

| Hook | Event | Description |
|------|-------|-------------|
| `notify.sh` | Notification | macOS sound alerts |
| `session_start.sh` | SessionStart | Inject historical session summaries |
| `guard_bash.sh` | PreToolUse(Bash) | Block dangerous commands |
| `guard_write.sh` | PreToolUse(Write/Edit) | Block junk file writes |
| `auto_check.sh` | PostToolUse(Edit/Write) | Auto lint after file modification |
| `pre_compact.sh` | PreCompact | Preserve key info before compaction |
| `stop.sh` | Stop | Save handoff summary |
| `cleanup_stop.sh` | Stop | Auto cleanup junk files |

## Configuration

### Global Setup (Recommended)

```bash
dock setup
```

This command does three things automatically:

1. **Install `dock` command** — Writes to `~/.local/bin/dock`, globally available
2. **Register MCP Server** — Writes to `~/.claude.json`, auto-connects on Claude Code startup
3. **Cleanup legacy** — Removes old `clm`/`claude-mgr` commands and MCP entries

```bash
dock setup --no-mcp      # Install command only, skip MCP
dock setup --no-bin      # Register MCP only, skip command
dock setup --no-cleanup  # Skip legacy cleanup
```

### Uninstall

```bash
dock teardown           # Remove MCP Server only
dock teardown --all     # Remove MCP + uninstall dock command
```

### Project-level Setup

```bash
dock init               # Full setup (MCP + Skills + Hooks + Git + Harness)
dock init --no-harness  # ocean-dock only, no Harness Engineering
dock init -s local      # Local project scope
dock init -t python     # Python project
```

### Manual MCP Registration

Add to `~/.claude.json` (global) or project `.claude/settings.json`:

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

If not in PATH, use absolute path:

```json
"command": "/path/to/ocean-duck/venv/bin/ocean-dock"
```

### Verify Connection

Restart Claude Code, then type `/mcp` to check if `ocean-dock` is connected. Once connected, AI can directly call 14 MCP Tools:

```
> Show me recent sessions
> Search historical conversations about "refactoring"
> Generate a handoff document from the last session
> Initialize harness engineering for this project
> Check which docs need to be synced after code changes
```

## Use with Ocean CLI

Ocean Dock is the companion tool for [Ocean CLI](https://github.com/ArtLjn/ocean-cc-cli), but also works standalone with vanilla Claude Code.

```
Ocean CLI (Host)                Ocean Dock (Companion)
├── Multi-model support        ├── Session Management
├── Auto Mode                  ├── Harness Engineering (22-file generator)
├── Dual-layer memory          ├── MCP Server (14 Tools)
├── Multi-model collaboration  ├── Hooks Automation
├── Skill system               ├── Skills System
└── Channel IM integration     └── Project Templates
```

## Keywords

`claude-code` `mcp-server` `session-manager` `harness-engineering` `developer-tools` `cli` `hooks` `skills` `python` `anthropic` `ai-assistant` `productivity` `automation` `code-review` `developer-experience` `ocean-cli`

`会话管理` `MCP工具` `Harness工程` `开发自动化` `Claude CLI` `AI编程助手`

## License

MIT
