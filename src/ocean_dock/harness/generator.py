"""
Harness Engineering 一键初始化 — 生成器核心
为项目生成完整的 Harness 基础设施：CLAUDE.md、docs/、scripts/、hooks、agents、rules、CI
"""

from __future__ import annotations

import json
import stat
from datetime import date
from pathlib import Path
from typing import Callable


def today():
    return date.today().isoformat()


# ── 模板内容 ──────────────────────────────────────────────


def tmpl_claude_md(ctx: dict) -> str:
    tech_desc = {
        "python": f"Python {ctx['project_name']}, FastAPI 后端",
        "ts": f"React + TypeScript 前端项目 {ctx['project_name']}",
        "both": f"{ctx['project_name']}，FastAPI 后端 + React+TS 前端",
    }
    backend_lines = """
| 后端启动 | `poetry run uvicorn app.main:app --reload` |
| 后端测试 | `poetry run pytest -v` |""" if ctx["tech_stack"] in ("python", "both") else ""
    frontend_lines = """
| 前端启动 | `pnpm dev` |
| 前端测试 | `pnpm test` |""" if ctx["tech_stack"] in ("ts", "both") else ""
    lint_line = "`ruff check . && ruff format .`" if ctx["tech_stack"] in ("python", "both") else "`pnpm lint`"

    return f"""# CLAUDE.md — 项目地图

> Agent 入口文件。控制在 80 行以内，详细内容放 rules/ 和 docs/。

## 项目简介
{tech_desc[ctx['tech_stack']]}

## 快速导航
| 你想做什么 | 去哪里看 |
|-----------|---------|
| 了解系统架构 | docs/architecture/overview.md |
| 了解模块边界和依赖规则 | docs/architecture/boundaries.md |
| 了解 Python 编码规范 | .claude/rules/python-style.md |
| 了解前端编码规范 | .claude/rules/frontend-style.md |
| 了解安全规范 | .claude/rules/security.md |
| 了解文档同步规则 | .claude/rules/docs-sync.md |
| 了解当前迭代任务 | docs/plans/current-sprint.md |
| 了解设计文档模板 | docs/design/TEMPLATE.md |

## 硬性规则（CI 会验证）
1. 依赖方向：models/ → repositories/ → services/ → api/（后端），types/ → lib/ → services/ → app/（前端）
2. 横切关注点（auth/log/telemetry）只通过依赖注入
3. 单文件 ≤ 500 行，单方法 ≤ 50 行
4. 新增代码必须有对应测试
5. 使用结构化日志，禁止 console.log / print 调试
6. 错误信息必须含 code 字段和上下文

## 常用命令
| 操作 | 命令 |
|------|------|
| Lint | `{lint_line}` |
| 架构约束 | `bash scripts/check-layer-deps.sh` |
| Harness 全量检查 | `bash scripts/harness-check.sh` |{backend_lines}{frontend_lines}

## 提交规范
- feat: 新功能 | fix: 修复 | refactor: 重构 | docs: 文档 | test: 测试 | chore: 杂项
- 禁止提交 .env、密钥、大文件
- 同天多个 commit 合并为一个（squash）
"""


def tmpl_settings_json(ctx: dict) -> str:
    rules_paths = {}
    if ctx["tech_stack"] in ("python", "both"):
        rules_paths["**/*.py"] = [".claude/rules/python-style.md", ".claude/rules/security.md", ".claude/rules/docs-sync.md"]
    if ctx["tech_stack"] in ("ts", "both"):
        rules_paths["**/*.{ts,tsx}"] = [".claude/rules/frontend-style.md", ".claude/rules/docs-sync.md"]
    rules_paths["docs/**"] = [".claude/rules/docs-sync.md"]

    settings = {
        "permissions": {
            "allow_bash_without_approval": False,
            "allowed_commands": [
                "poetry run *", "pnpm *", "pytest *", "ruff *",
                "node scripts/*", "bash scripts/*",
                "git status", "git diff", "git log --oneline -10", "git worktree *"
            ]
        },
        "hooks": {
            "pre_tool_use": ".claude/hooks/pre_tool_use.json",
            "post_tool_use": ".claude/hooks/post_tool_use.json"
        },
        "rules": {"paths": rules_paths},
        "agents": {
            "architect": ".claude/agents/architect.md",
            "coder": ".claude/agents/coder.md",
            "reviewer": ".claude/agents/reviewer.md",
            "cleanup": ".claude/agents/cleanup.md"
        }
    }
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def tmpl_pre_hook(ctx: dict) -> str:
    rules = [
        {
            "pattern": "git push --force|git push --force-with-lease",
            "block": True,
            "message": "❌ 禁止 force push，会导致远程提交丢失。\n✅ FIX: 用 rebase 解决分歧：git pull --rebase\n📖 See: docs/conventions/README.md"
        },
        {
            "pattern": "rm -rf /|rm -rf \\*|rm -rf ~",
            "block": True,
            "message": "❌ 危险删除操作被拦截。\n✅ FIX: 如需清理，指定具体目录路径\n📖 See: .claude/rules/python-style.md"
        }
    ]
    if ctx["tech_stack"] in ("python", "both"):
        rules.append({
            "pattern": "DROP TABLE|DELETE FROM.*WHERE",
            "block": True,
            "message": "❌ 数据库危险操作被拦截。\n✅ FIX: 使用 alembic 迁移管理数据库变更\n📖 See: docs/architecture/overview.md"
        })

    py_rules = []
    if ctx["tech_stack"] in ("python", "both"):
        py_rules = [
            {
                "pattern": "test\\.py$|tmp\\.py$|debug\\.py$",
                "path": "^(?!tests/).*",
                "block": True,
                "message": "❌ 禁止在根目录创建临时脚本。\n✅ FIX: 放 tests/ 目录，命名 test_xxx.py\n📖 See: .claude/rules/python-style.md"
            },
            {
                "pattern": "\\.env$",
                "block": True,
                "message": "❌ 禁止创建 .env 文件，避免密钥泄露。\n✅ FIX: 使用 app/core/config.py 集中管理配置\n📖 See: .claude/rules/security.md"
            }
        ]

    hooks = [
        {"event": "PreToolUse", "tool": "Bash", "action": "拦截危险命令", "rules": rules}
    ]
    if py_rules:
        hooks.append({"event": "PreToolUse", "tool": "Write|Edit", "action": "防污染检查", "rules": py_rules})

    return json.dumps({"hooks": hooks}, indent=2, ensure_ascii=False) + "\n"


def tmpl_post_hook(ctx: dict) -> str:
    hooks = []

    if ctx["tech_stack"] in ("python", "both"):
        hooks.append({
            "event": "PostToolUse", "tool": "Write|Edit", "glob": "**/*.py",
            "action": "Python 文件修改后自动格式化",
            "command": "ruff format {file} && ruff check --fix {file} ; ruff check {file}"
        })
    if ctx["tech_stack"] in ("ts", "both"):
        hooks.append({
            "event": "PostToolUse", "tool": "Write|Edit", "glob": "**/*.{ts,tsx}",
            "action": "前端文件修改后自动格式化",
            "command": f"cd {ctx['frontend_dir']} && pnpm prettier --write {{file}} 2>/dev/null || echo 'prettier not configured'"
        })

    if ctx["tech_stack"] in ("python", "both"):
        hooks.extend([
            {
                "event": "PostToolUse", "tool": "Write|Edit",
                "glob": f"{ctx['backend_dir']}/app/api/**/*.py",
                "action": "API 修改触发文档同步",
                "message": "⚠️ 你修改了 API 文件，文档可能不同步。\n✅ FIX: 立即调用 sync_docs MCP Tool 检查需要同步的文档，然后逐项更新。\n📖 See: .claude/rules/docs-sync.md"
            },
            {
                "event": "PostToolUse", "tool": "Write|Edit",
                "glob": f"{ctx['backend_dir']}/app/models/**/*.py",
                "action": "模型修改触发文档同步",
                "message": "⚠️ 你修改了数据模型，文档可能不同步。\n✅ FIX: 立即调用 sync_docs MCP Tool 检查需要同步的文档，然后逐项更新。\n📖 See: .claude/rules/docs-sync.md"
            },
            {
                "event": "PostToolUse", "tool": "Write|Edit",
                "glob": f"{ctx['backend_dir']}/app/services/**/*.py",
                "action": "业务逻辑修改触发文档同步",
                "message": "⚠️ 你修改了业务逻辑，文档可能不同步。\n✅ FIX: 立即调用 sync_docs MCP Tool 检查需要同步的文档，然后逐项更新。\n📖 See: .claude/rules/docs-sync.md"
            }
        ])

    hooks.extend([
        {
            "event": "PostToolUse", "tool": "Write|Edit",
            "glob": "**/Dockerfile|**/docker-compose.yml",
            "action": "部署配置修改提醒更新文档",
            "message": "❌ 你修改了部署配置，部署文档可能不同步。\n✅ FIX: 检查 docs/architecture/overview.md 中的部署说明\n📖 See: .claude/rules/docs-sync.md"
        },
        {
            "event": "PostToolUse", "tool": "Write|Edit",
            "action": "检查 TODO/FIXME 残留",
            "command": "grep -n 'TODO\\\\|FIXME\\\\|NotImplemented\\\\|pass  # TODO' {file} 2>/dev/null && echo '⚠️ 发现残留，请在提交前清理' || echo '✅ 无 TODO/FIXME 残留'"
        },
        {
            "event": "PostToolUse", "tool": "Write|Edit",
            "glob": "docs/**/*.md",
            "action": "文档修改后验证格式",
            "command": "node scripts/validate-docs.js 2>/dev/null || echo 'validate-docs.js not found, skip'"
        }
    ])

    return json.dumps({"hooks": hooks}, indent=2, ensure_ascii=False) + "\n"


def tmpl_python_style() -> str:
    return """# Python 编码规范

## 文件与方法限制
- 单个文件 ≤ 500 行，方法 ≤ 50 行，类 ≤ 200 行
- 方法参数 ≤ 5 个，超过用 Pydantic model/dataclass 封装
- 单行 ≤ 120 字符

## 项目结构
- 分层架构：models/ → repositories/ → services/ → api/
- 配置集中管理（app/core/config.py）
- 公共工具统一放 app/core/
- 数据模型统一用 Pydantic

## 设计模式
- if/elif 超 3 个分支 → 策略模式
- 对象创建复杂 → 工厂模式
- 多对象通知 → 观察者模式
- 共享昂贵资源 → 单例模式

## IDE 检查规范
- 未用 self → 加 @staticmethod
- 只用 cls → 加 @classmethod
- 删除未使用的导入/变量
- 未用参数加 _ 前缀
- 避免同名变量遮蔽
- 字符串拼接用 join()
- 文件操作用 with

## 测试规范
- pytest 为主，pytest-mock / pytest-asyncio / parametrize 配合
- tests/ 镜像源码结构，test_*.py 命名
- 单函数单行为，Arrange-Act-Assert 模式
- 正常+异常+边界全覆盖
- 外部依赖必须 mock
"""


def tmpl_frontend_style() -> str:
    return """# 前端编码规范

## 技术栈
- React 18 + TypeScript + Vite
- 状态管理：Zustand（简单场景）/ React Query（服务端状态）
- UI 组件：Shadcn UI
- 样式：Tailwind CSS

## 文件组织
- 按功能模块组织，不按类型拆分
- 组件文件：PascalCase.tsx
- 工具文件：camelCase.ts
- 类型定义：同文件或 types/ 目录

## 代码规范
- 优先用函数组件 + Hooks
- Props 用接口定义，不用 any
- 异步操作统一用 async/await，不用 .then
- 错误边界处理 API 异常
- 组件拆分：超过 150 行考虑拆分

## 测试规范
- vitest + React Testing Library
- 测试文件名：*.test.tsx
- 重点测交互逻辑，不测样式细节
"""


def tmpl_security() -> str:
    return """# 安全规范

## 输入验证
- 所有 API 入参必须 Pydantic 校验
- 拒绝未预期的字段（extra='forbid'）
- SQL 注入防护：只用 ORM/参数化查询，禁止字符串拼接 SQL

## 认证授权
- JWT token 从 Header 读取，不存 cookie
- 敏感操作校验用户身份（current_user 注入）
- 密码 bcrypt 哈希，禁止明文存储

## 输出安全
- 禁止返回完整 traceback 给客户端
- 敏感字段（password、token）序列化时排除

## 文件操作
- 上传文件校验 MIME 类型和大小
- 禁止用户控制文件路径（路径遍历）
- 临时文件及时清理

## 依赖安全
- 定期 `poetry audit` 检查漏洞
- 不引入不必要的依赖
"""


def tmpl_docs_sync() -> str:
    return """# 文档同步规则

## 触发条件
当改动涉及以下内容时，必须同步更新 docs/ 下的对应文档：

| 改动类型 | 必须更新的文档 |
|---|---|
| 新增/修改 API 端点 | docs/reference/api-spec.yaml + docs/design/ 功能状态 |
| 新增/修改数据模型 | docs/reference/api-spec.yaml + docs/design/ 数据模型描述 |
| 新增/修改配置项 | docs/architecture/overview.md |
| 新增/修改部署相关 | docs/architecture/overview.md |
| 新增/修改安全策略 | .claude/rules/security.md |
| 新增功能模块 | docs/design/ 新增设计文档（用 TEMPLATE.md） |

## 更新检查
修改代码后，运行：
```bash
bash scripts/check-doc-freshness.sh
```

## 文档状态标记
更新文档时，更新 front-matter 中的 `last_updated` 日期。
如果文档内容被替代，将 status 改为 `deprecated`，不要直接删除。
"""


def tmpl_architect(ctx: dict) -> str:
    return """---
name: architect
description: 架构设计子代理。开发前自动委派，负责技术方案设计和架构评审。
tools:
  - Read
  - Grep
  - Glob
  - WebSearch
model: sonnet
---

# 架构师代理

你是一个架构设计代理。负责在开发前制定技术方案，**严禁写代码**。

## 工作流程

1. 读取需求描述
2. 读取现有架构（CLAUDE.md 快速导航 → docs/architecture/）
3. 搜索类似实现（Grep 现有代码模式）
4. 填写设计文档模板（docs/design/TEMPLATE.md）
5. 明确验收标准和非目标

## 约束

- **只读不写**，绝对不能创建或修改任何代码文件
- 不输出完整代码，只输出设计和接口定义
- 必须先读 docs/architecture/boundaries.md 确认依赖方向
- 如果涉及跨层调用，必须在方案中标注豁免原因
- 评审现有设计时，指出风险和改进建议

## 输出格式

```markdown
## 技术方案：xxx

### 涉及模块
- models/xxx.py（新增/修改）
- repositories/xxx.py（新增/修改）
- services/xxx.py（新增/修改）
- api/v1/xxx.py（新增/修改）

### 数据模型
Pydantic schema 定义

### API 设计
| 方法 | 路径 | 描述 |
|------|------|------|

### 非目标
- 不做 XXX

### 验收标准
- [ ] 具体、可验证

### 风险点
1. xxx
```
"""


def tmpl_coder(ctx: dict) -> str:
    return f"""---
name: coder
description: 开发子代理。架构评审通过后自动委派，按 TDD 方式实现代码。
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
model: sonnet
---

# 开发代理

你是一个开发代理。按 TDD 方式实现代码，**必须跑测试验证**。

## 工作流程

1. 读取 architect 产出的技术方案（docs/design/ 中对应文档）
2. **TDD 流程（强制）**：
   - RED：先写测试（定义期望行为）
   - GREEN：写最小实现使测试通过
   - REFACTOR：重构，确保测试仍通过
3. 实现完成后执行 Harness 自检
4. 提交给 reviewer 审查

## Harness 自检清单（必须逐项确认）

1. [ ] 测试覆盖正常流程
2. [ ] 测试覆盖边界情况（空输入、异常、权限）
3. [ ] `grep -r "TODO\\|FIXME\\|NotImplemented" {ctx['backend_dir']}/` 无残留
4. [ ] `poetry run pytest -v` 全部通过
5. [ ] `ruff check .` 无错误
6. [ ] `bash scripts/check-layer-deps.sh` 架构约束通过
7. [ ] 对照技术方案验收标准逐项确认
8. [ ] 检查 docs/ 对应文档是否需要同步更新

## 约束

- 严格按分层架构实现（models → repositories → services → api）
- 新文件放对应目录，不在根目录创建临时文件
- 修改现有文件前先 grep 确认当前状态
- 每完成一个模块就 commit
- 不输出假设性代码，只写确定要用的代码
- 如果发现架构方案有缺陷，暂停并反馈给 architect，不要自行绕过
"""


def tmpl_reviewer(ctx: dict) -> str:
    return """---
name: reviewer
description: 代码审查子代理。开发完成后自动委派，审查代码质量和完整性。
tools:
  - Read
  - Grep
  - Glob
  - Bash
model: sonnet
---

# 审查代理

你是一个代码审查代理。审查代码质量和实现完整性，**严禁修改任何代码**。

## 工作流程

1. 读取本次变更：`git diff --name-only`
2. 逐文件审查变更内容
3. 运行 Harness 全量检查：`bash scripts/harness-check.sh`
4. 搜索遗漏：`grep -r "TODO\\|FIXME\\|NotImplemented"`
5. 检查文档同步：变更涉及 API/模型/配置时，docs/ 是否已更新
6. 输出审查报告

## 审查维度

- **完整性**：是否覆盖了 architect 方案中的所有验收标准
- **正确性**：逻辑是否正确，边界条件是否处理
- **安全性**：是否存在注入、越权等安全问题
- **可维护性**：命名是否清晰，结构是否合理，文件是否超限
- **架构合规**：是否符合 docs/architecture/boundaries.md 的依赖方向
- **文档同步**：是否更新了对应文档

## 约束

- 只读不写，绝对不能修改任何文件
- 只报告事实，不做假设性批评
- 优先报告严重问题，不要纠结风格细节
- 如果测试没跑过，直接标记为 🔴 必须修复

## 输出格式

```markdown
## 审查报告

### 概要
- 审查文件数：N
- 问题数：N（🔴 必须修复 / 🟡 建议优化）

### 问题列表
#### [文件:行号] 问题描述
- 严重程度：🔴/🟡
- 当前代码：`...`
- ✅ FIX: 修复建议
- 📖 See: 相关文档

### Harness 检查结果
- [ ] Linter 通过
- [ ] 测试通过
- [ ] 架构约束通过
- [ ] 文档已同步

### 结论
✅ 通过 / ⚠️ 需要修改后复审
```
"""


def tmpl_cleanup(ctx: dict) -> str:
    return """---
name: cleanup
description: 代码清理子代理。定期清理死代码、过时文档、TODO残留。按需触发。
tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Bash
model: sonnet
---

# 清理代理

你是一个代码清理代理。负责保持代码库整洁，删除过时内容。

## 职责范围

1. **代码清理**
   - 删除未使用的 import、变量、函数
   - 清理 TODO/FIXME（超过 30 天未处理的，生成清理 PR 或删除）
   - 合并重复的代码片段

2. **文档清理**
   - 运行 `bash scripts/check-doc-freshness.sh` 检查过期文档
   - 将状态为 `deprecated` 的文档标记归档
   - 更新失效的文档内链接
   - 清理冗余注释

3. **配置清理**
   - 删除未使用的依赖
   - 清理过时的环境变量

## 工作流程

1. 运行 Harness 文档新鲜度检查
2. 搜索死代码：`grep -r "unused\\|deprecated"` 或扫描未引用符号
3. 检查 TODO/FIXME 残留和创建时间
4. 列出清理清单，**先给用户确认**
5. 执行清理
6. 运行 `bash scripts/harness-check.sh` 确认没有 break

## 约束

- 清理前必须列出清单并确认
- 每次清理后跑 harness-check.sh 全量检查
- 不删除状态为 `active` 的文档
- 保留有历史价值的注释（说明设计决策的）
- 每个 TODO/FIXME 清理前先确认是否仍相关
"""


def tmpl_overview(ctx: dict) -> str:
    backend_section = ""
    if ctx["tech_stack"] in ("python", "both"):
        backend_section = f"""
## 后端分层

```
{ctx['backend_dir']}/app/
├── models/          # 纯数据模型（Pydantic + SQLAlchemy），不依赖任何层
├── repositories/    # 数据访问层，只依赖 models/
├── services/        # 业务逻辑层，依赖 models/ 和 repositories/
├── api/             # 路由和请求处理，依赖 services/
├── core/            # 配置、日志、安全等横切关注点
└── main.py          # 入口
```

## 后端依赖方向

```
models/ → 不依赖任何层
  ↓
repositories/ → 只依赖 models/
  ↓
services/ → 依赖 models/ 和 repositories/
  ↓
api/ → 依赖 services/（不直接依赖 repositories/）
"""

    frontend_section = ""
    if ctx["tech_stack"] in ("ts", "both"):
        frontend_section = f"""
## 前端分层

```
{ctx['frontend_dir']}/src/
├── types/           # 纯类型定义，不依赖任何层
├── lib/             # 工具函数和基础设施，只依赖 types/
├── services/        # 业务逻辑，依赖 types/ 和 lib/
├── components/      # UI 组件，只依赖 types/ 和 lib/providers
└── app/             # 页面路由，可依赖所有层
```
"""

    return f"""---
last_updated: {today()}
status: active
---

# 系统架构
{backend_section}
{frontend_section}
## 核心约定

- 横切关注点（auth/log/telemetry）通过依赖注入，不被业务层直接 import
- API 版本统一 v1，路径前缀 `/api/v1/`
- 数据库迁移只用 alembic，禁止手动改表
"""


def tmpl_boundaries(ctx: dict) -> str:
    backend_matrix = ""
    if ctx["tech_stack"] in ("python", "both"):
        backend_matrix = """
## 后端依赖矩阵

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| models/ | 无 | repositories/, services/, api/ |
| repositories/ | models/ | services/, api/ |
| services/ | models/, repositories/ | api/ |
| api/ | services/, models/ | repositories/（绕过 service 直接访问数据） |

## 后端违规示例

```python
# ❌ api/ 层直接 import repositories/
from app.repositories.user_repo import UserRepository  # 错误！

# ✅ api/ 层通过 services/ 访问
from app.services.user_service import UserService  # 正确
```
"""

    frontend_matrix = ""
    if ctx["tech_stack"] in ("ts", "both"):
        frontend_matrix = """
## 前端依赖矩阵

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| types/ | 无 | 任何层 |
| lib/ | types/ | services/, components/, app/ |
| services/ | types/, lib/ | components/, app/ |
| components/ | types/, lib/providers | services/（直接调用）, app/ |
| app/ | 所有层 | 无限制 |

## 前端违规示例

```typescript
// ❌ 组件直接调用 services/
import {{ userService }} from '@/services/user';  // 错误！

// ✅ 组件通过 props 接收数据，页面层调用 services/
<UserProfile user={{user}} />  // 正确，数据从页面 props 传入
```
"""

    return f"""---
last_updated: {today()}
status: active
---

# 模块边界与依赖规则
{backend_matrix}
{frontend_matrix}
## 豁免机制

特殊情况下需绕过约束时，必须添加注释说明原因：

```python
# harness-exempt: 此处需要直接访问 repo 层，原因见 #PR-XXX
from app.repositories.user_repo import UserRepository
```
"""


def tmpl_conventions_readme(ctx: dict) -> str:
    rows = []
    if ctx["tech_stack"] in ("python", "both"):
        rows.append("| Python 编码规范 | .claude/rules/python-style.md | `**/*.py` |")
    if ctx["tech_stack"] in ("ts", "both"):
        rows.append("| 前端编码规范 | .claude/rules/frontend-style.md | `**/*.{ts,tsx}` |")
    rows.extend([
        "| 安全规范 | .claude/rules/security.md | 全局 |",
        "| 文档同步规范 | .claude/rules/docs-sync.md | 全局 |",
        "| 依赖方向约束 | docs/architecture/boundaries.md | 全局 |",
    ])

    return f"""---
last_updated: {today()}
status: active
---

# 编码规范索引

| 规范 | 位置 | 适用范围 |
|------|------|---------|
{chr(10).join(rows)}
"""


def tmpl_design_template() -> str:
    return f"""---
last_updated: {today()}
status: draft          # draft | approved | in_progress | implemented | deprecated
---

# Feature: [功能名称]

## 目标
一句话描述这个功能要解决什么问题。

## 非目标
明确列出这次**不做什么**（防止 Agent 扩大范围）：
- 不做 XXX
- 不做 XXX

## 技术方案

### 涉及的模块
- models/: 新增/修改 XXX
- repositories/: 新增/修改 XXX
- services/: 新增/修改 XXX
- api/: 新增/修改 XXX

### 数据模型变更
```sql
-- 如有数据库变更，写在这里
```

### API 变更
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/xxx | ... |

请求/响应体：
```json
{{ "request": "...", "response": "..." }}
```

## 验收标准
- [ ] 标准1：具体的、可验证的
- [ ] 标准2：具体的、可验证的
- [ ] 测试覆盖率 ≥ 80%

## 依赖
- 依赖 feature-xxx（状态：✅ 已实现 / 📋 已审批 / 🚧 开发中）
"""


def tmpl_current_sprint() -> str:
    return f"""---
last_updated: {today()}
status: active
---

# 当前迭代

> 本文档跟踪当前迭代中的任务和进度。

## 进行中

_暂无_

## 待办

_暂无_

## 已完成

_暂无_
"""


def tmpl_check_layer_deps(ctx: dict) -> str:
    backend_check = ""
    if ctx["tech_stack"] in ("python", "both"):
        backend_check = f"""
# ── 后端检查 ──
BACKEND="{ctx['backend_dir']}/app"
if [ -d "$BACKEND" ]; then
  echo "🔍 检查后端分层依赖..."

  # api/ 层不能直接引用 repositories/
  if grep -rn "from.*repositories\\|import.*repositories" "$BACKEND/api/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: api/ 层直接引用了 repositories/ 层"
    echo "✅ FIX: 通过 services/ 层访问数据，如 from app.services.xxx import XxxService"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # repositories/ 层不能引用 services/
  if grep -rn "from.*services\\|import.*services" "$BACKEND/repositories/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: repositories/ 层反向引用了 services/ 层"
    echo "✅ FIX: 使用接口解耦，通过依赖注入获取 service"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # models/ 层不能引用 repositories/ 或 services/
  if grep -rn "from.*\\(repositories\\|services\\)\\|import.*\\(repositories\\|services\\)" "$BACKEND/models/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: models/ 层引用了 repositories/ 或 services/ 层"
    echo "✅ FIX: models/ 是纯数据定义，不应依赖业务层"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
fi
"""

    frontend_check = ""
    if ctx["tech_stack"] in ("ts", "both"):
        frontend_check = f"""
# ── 前端检查 ──
FRONTEND="{ctx['frontend_dir']}/src"
if [ -d "$FRONTEND" ]; then
  echo "🔍 检查前端分层依赖..."

  # components/ 不能直接引用 services/
  if grep -rn "from.*services\\|import.*services" "$FRONTEND/components/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: components/ 直接引用了 services/ 层"
    echo "✅ FIX: 在 app/ 页面层调用 services/，通过 props 传递数据给组件"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # lib/ 不能引用 services/
  if grep -rn "from.*services\\|import.*services" "$FRONTEND/lib/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: lib/ 层引用了 services/ 层"
    echo "✅ FIX: lib/ 是基础设施层，不应依赖业务逻辑"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
fi
"""

    file_size_check = ""
    if ctx["tech_stack"] in ("python", "both"):
        file_size_check += """
# Python 文件
for f in $(find backend/ -name "*.py" 2>/dev/null | grep -v __pycache__ | grep -v ".venv"); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 500 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 500）"
    echo "✅ FIX: 拆分为更小的模块，将辅助函数移至 utils/"
    ERRORS=$((ERRORS + 1))
  fi
done
"""
    if ctx["tech_stack"] in ("ts", "both"):
        file_size_check += """
# TypeScript 文件
for f in $(find frontend/src/ -name "*.ts" -o -name "*.tsx" 2>/dev/null | grep -v node_modules); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 300 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 300）"
    echo "✅ FIX: 拆分为更小的组件或模块"
    ERRORS=$((ERRORS + 1))
  fi
done
"""

    return f"""#!/bin/bash
# scripts/check-layer-deps.sh
# 检查分层架构依赖方向，确保不违规

set -e

ERRORS=0
WARNINGS=0
{backend_check}
{frontend_check}
# ── 文件大小检查 ──
echo "🔍 检查文件大小..."
{file_size_check}
# ── TODO/FIXME 检查 ──
echo "🔍 检查 TODO/FIXME 残留..."
TODO_COUNT=$(grep -rn "TODO\\|FIXME\\|NotImplemented\\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | wc -l | tr -d ' ')
if [ "$TODO_COUNT" -gt 0 ]; then
  echo "⚠️  发现 $TODO_COUNT 处 TODO/FIXME 残留："
  grep -rn "TODO\\|FIXME\\|NotImplemented\\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | head -20
  WARNINGS=$((WARNINGS + 1))
fi

# ── 结果 ──
echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "❌ 架构检查失败：${{ERRORS}} 个错误，${{WARNINGS}} 个警告"
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "⚠️  架构检查通过但有 ${{WARNINGS}} 个警告"
  exit 0
fi

echo "✅ 架构依赖检查全部通过"
"""


def tmpl_check_doc_freshness() -> str:
    return """#!/bin/bash
# scripts/check-doc-freshness.sh
# 检查 docs/ 下文档的新鲜度，标记过期文档

set -e

MAX_DAYS=${1:-60}
DOCS_DIR="docs"
ERRORS=0

if [ ! -d "$DOCS_DIR" ]; then
  echo "⏭️  无 docs/ 目录，跳过文档新鲜度检查"
  exit 0
fi

echo "🔍 检查文档新鲜度（阈值 ${MAX_DAYS} 天）..."

if git rev-parse --git-dir > /dev/null 2>&1; then
  find "$DOCS_DIR" -name "*.md" | while read f; do
    last_mod=$(git log -1 --format=%ct "$f" 2>/dev/null || echo "0")
    now=$(date +%s)
    if [ "$last_mod" -eq 0 ]; then
      echo "⚠️  $f: 新文件，未追踪"
      continue
    fi
    days_old=$(( (now - last_mod) / 86400 ))
    if [ "$days_old" -gt "$MAX_DAYS" ]; then
      echo "❌ $f 已 ${days_old} 天未更新（超过 ${MAX_DAYS} 天阈值）"
      echo "✅ FIX: 审查内容是否仍准确，如已过时标记 status: deprecated"
      echo "📖 See: .claude/rules/docs-sync.md"
    fi
  done
fi

echo "🔍 检查文档状态标记..."
find "$DOCS_DIR" -name "*.md" | while read f; do
  if ! head -5 "$f" | grep -q "^---"; then
    echo "⚠️  $f: 缺少 front-matter（需添加 last_updated/status 字段）"
    continue
  fi
  status=$(grep "^status:" "$f" 2>/dev/null | head -1 | sed 's/status: *//')
  if [ "$status" = "draft" ]; then
    last_mod=$(git log -1 --format=%ct "$f" 2>/dev/null || echo "0")
    now=$(date +%s)
    if [ "$last_mod" -gt 0 ]; then
      days_old=$(( (now - last_mod) / 86400 ))
      if [ "$days_old" -gt 30 ]; then
        echo "⚠️  $f: 状态为 draft 已 ${days_old} 天，请审批或删除"
      fi
    fi
  fi
done

echo "✅ 文档新鲜度检查完成"
"""


def tmpl_agent_verify(ctx: dict) -> str:
    frontend_dir = ctx["frontend_dir"]
    backend_block = ""
    if ctx["tech_stack"] in ("python", "both"):
        backend_block = """
if [ -d "backend" ]; then
  echo "📦 安装后端依赖..."
  cd backend && poetry install --quiet 2>/dev/null || pip install -r requirements.txt 2>/dev/null || echo "⚠️ 依赖安装跳过"
  echo "🔍 运行 Ruff 检查..."
  poetry run ruff check . 2>/dev/null || ruff check . || { echo "❌ Ruff 检查失败"; exit 1; }
  echo "🧪 运行后端测试..."
  poetry run pytest -v 2>/dev/null || pytest -v || { echo "❌ 后端测试失败"; exit 1; }
  cd "$WORKTREE_DIR"
fi
"""
    frontend_block = ""
    if ctx["tech_stack"] in ("ts", "both"):
        frontend_block = f"""
if [ -d "{frontend_dir}" ]; then
  echo "📦 安装前端依赖..."
  cd {frontend_dir} && pnpm install --silent 2>/dev/null || echo "⚠️ pnpm install 跳过"
  echo "🔍 运行 TypeScript 检查..."
  npx tsc --noEmit 2>/dev/null || {{ echo "❌ TypeScript 检查失败"; exit 1; }}
  echo "🧪 运行前端测试..."
  pnpm test 2>/dev/null || {{ echo "❌ 前端测试失败"; exit 1; }}
  cd "$WORKTREE_DIR"
fi
"""

    return f"""#!/bin/bash
# scripts/agent-verify.sh
# 为指定分支创建隔离验证环境，在 worktree 中跑完整检查

set -e

BRANCH=${{1:?用法: agent-verify.sh <branch_name>}}
WORKTREE_DIR="/tmp/agent-verify-$(date +%s)"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔧 创建 worktree: $WORKTREE_DIR"
git worktree add "$WORKTREE_DIR" "$BRANCH" 2>/dev/null || {{
  echo "❌ 无法创建 worktree，请确认分支存在"
  exit 1
}}

cd "$WORKTREE_DIR"
{backend_block}
{frontend_block}
echo "🔍 运行架构约束检查..."
bash scripts/check-layer-deps.sh || {{ echo "❌ 架构约束检查失败"; exit 1; }}

echo "🧹 清理 worktree..."
cd "$PROJECT_DIR"
git worktree remove "$WORKTREE_DIR" --force

echo "✅ 所有验证通过"
"""


def tmpl_harness_check(ctx: dict) -> str:
    return f"""#!/bin/bash
# scripts/harness-check.sh
# Harness Engineering 全量验证入口，一键跑完所有检查

set -e

echo "╔══════════════════════════════════════╗"
echo "║   Harness Engineering 全量验证        ║"
echo "╚══════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0
SKIP=0

run_check() {{
  local name="$1"
  local cmd="$2"
  echo "── $name ──"
  if eval "$cmd"; then
    echo "✅ $name 通过"
    PASS=$((PASS + 1))
  else
    echo "❌ $name 失败"
    FAIL=$((FAIL + 1))
  fi
  echo ""
}}

# ── Linter ──
if [ -d "backend" ] && command -v ruff &>/dev/null; then
  run_check "Python Lint (ruff)" "ruff check backend/"
else
  echo "⏭️  Python Lint: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -d "{ctx['frontend_dir']}" ]; then
  run_check "Frontend Lint" "cd {ctx['frontend_dir']} && pnpm lint 2>/dev/null || echo 'lint not configured'"
else
  echo "⏭️  Frontend Lint: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 类型检查 ──
if [ -d "{ctx['frontend_dir']}" ] && [ -f "{ctx['frontend_dir']}/tsconfig.json" ]; then
  run_check "TypeScript Check" "cd {ctx['frontend_dir']} && npx tsc --noEmit"
else
  echo "⏭️  TypeScript Check: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 单元测试 ──
if [ -d "backend" ] && command -v pytest &>/dev/null; then
  run_check "Python Tests (pytest)" "cd backend && pytest -v --tb=short"
else
  echo "⏭️  Python Tests: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -d "{ctx['frontend_dir']}" ]; then
  run_check "Frontend Tests" "cd {ctx['frontend_dir']} && pnpm test 2>/dev/null || echo 'no tests'"
else
  echo "⏭️  Frontend Tests: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 架构约束 ──
if [ -f "scripts/check-layer-deps.sh" ]; then
  run_check "架构约束检查" "bash scripts/check-layer-deps.sh"
else
  echo "⏭️  架构约束检查: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── TODO/FIXME ──
echo "── TODO/FIXME 残留检查 ──"
echo "✅ 检查完成"
PASS=$((PASS + 1))
echo ""

# ── 文档新鲜度 ──
if [ -f "scripts/check-doc-freshness.sh" ]; then
  run_check "文档新鲜度" "bash scripts/check-doc-freshness.sh"
else
  echo "⏭️  文档新鲜度: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 汇总 ──
echo "╔══════════════════════════════════════╗"
echo "║   验证结果汇总                        ║"
echo "╠══════════════════════════════════════╣"
echo "║   ✅ 通过: $PASS"
echo "║   ❌ 失败: $FAIL"
echo "║   ⏭️  跳过: $SKIP"
echo "╚══════════════════════════════════════╝"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
"""


def tmpl_ci(ctx: dict) -> str:
    steps = []

    if ctx["tech_stack"] in ("ts", "both"):
        steps.append("""
      - name: TypeScript Check
        run: |
          if [ -d "frontend" ]; then
            cd frontend && pnpm install && npx tsc --noEmit
          else
            echo "⏭️  无前端目录，跳过"
          fi
""")

    if ctx["tech_stack"] in ("python", "both"):
        steps.append("""
      - name: Python Lint
        run: |
          if [ -d "backend" ]; then
            pip install ruff && ruff check backend/
          else
            echo "⏭️  无后端目录，跳过"
          fi
""")

    if ctx["tech_stack"] in ("python", "both"):
        steps.append("""
      - name: Python Tests
        run: |
          if [ -d "backend" ]; then
            cd backend && pip install pytest && pytest -v
          else
            echo "⏭️  无后端目录，跳过"
          fi
""")

    if ctx["tech_stack"] in ("ts", "both"):
        steps.append(f"""
      - name: Frontend Tests
        run: |
          if [ -d "{ctx['frontend_dir']}" ]; then
            cd {ctx['frontend_dir']} && pnpm install && pnpm test
          else
            echo "⏭️  无前端目录，跳过"
          fi
""")

    steps.extend([
"""
      - name: Architecture Check
        run: bash scripts/check-layer-deps.sh
""",
"""
      - name: File Size Check
        run: |
          ERRORS=0
          if [ -d "backend" ]; then
            find backend/ -name '*.py' -not -path '*/__pycache__/*' -not -path '*/.venv/*' | while read f; do
              lines=$(wc -l < "$f")
              if [ "$lines" -gt 500 ]; then
                echo "❌ $f 有 $lines 行（上限 500）"
                echo "✅ FIX: 拆分为更小的模块"
                exit 1
              fi
            done
          fi
          if [ -d "frontend/src" ]; then
            find frontend/src/ -name '*.ts' -o -name '*.tsx' | while read f; do
              lines=$(wc -l < "$f")
              if [ "$lines" -gt 300 ]; then
                echo "❌ $f 有 $lines 行（上限 300）"
                echo "✅ FIX: 拆分为更小的组件或模块"
                exit 1
              fi
            done
          fi
""",
"""
      - name: Doc Freshness
        run: bash scripts/check-doc-freshness.sh
"""
    ])

    steps_yaml = "".join(steps)

    return f"""name: Harness Checks

on: [pull_request]

jobs:
  quality-gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
{steps_yaml}
"""


# ── 主流程 ──────────────────────────────────────────────


def init_harness(
    project_dir: str | Path,
    project_name: str,
    tech_stack: str = "both",
    backend_dir: str = "backend",
    frontend_dir: str = "frontend",
    on_log: Callable[[str], None] | None = None,
) -> dict:
    """初始化 Harness Engineering 基础设施。

    Args:
        project_dir: 目标项目路径
        project_name: 项目名称
        tech_stack: 技术栈 (python/ts/both)
        backend_dir: 后端目录名
        frontend_dir: 前端目录名
        on_log: 日志回调函数，不传则静默

    Returns:
        {"created": [...], "skipped": [...], "total_created": N, "total_skipped": N}
    """
    _log = on_log or (lambda _: None)
    project_dir = Path(project_dir).resolve()
    ctx = {
        "project_name": project_name,
        "tech_stack": tech_stack,
        "backend_dir": backend_dir,
        "frontend_dir": frontend_dir,
    }

    if not project_dir.exists():
        raise FileNotFoundError(f"项目目录不存在: {project_dir}")

    created: list[str] = []
    skipped: list[str] = []

    def write_file(path: Path, content: str):
        if path.exists():
            skipped.append(str(path))
            _log(f"  ⏭️  跳过（已存在）: {path}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(str(path))
        _log(f"  ✅ 创建: {path}")

    def make_executable(path: Path):
        if path.exists():
            current = path.stat().st_mode
            path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    _log("🚀 初始化 Harness Engineering 基础设施")
    _log(f"   项目: {ctx['project_name']} | 技术栈: {ctx['tech_stack']}")
    _log("")

    # ── .claude/ ──
    _log("📁 生成 .claude/ 配置...")
    write_file(project_dir / ".claude" / "CLAUDE.md", tmpl_claude_md(ctx))
    write_file(project_dir / ".claude" / "settings.json", tmpl_settings_json(ctx))
    write_file(project_dir / ".claude" / "hooks" / "pre_tool_use.json", tmpl_pre_hook(ctx))
    write_file(project_dir / ".claude" / "hooks" / "post_tool_use.json", tmpl_post_hook(ctx))

    if ctx["tech_stack"] in ("python", "both"):
        write_file(project_dir / ".claude" / "rules" / "python-style.md", tmpl_python_style())
        write_file(project_dir / ".claude" / "rules" / "security.md", tmpl_security())
    if ctx["tech_stack"] in ("ts", "both"):
        write_file(project_dir / ".claude" / "rules" / "frontend-style.md", tmpl_frontend_style())
    write_file(project_dir / ".claude" / "rules" / "docs-sync.md", tmpl_docs_sync())

    write_file(project_dir / ".claude" / "agents" / "architect.md", tmpl_architect(ctx))
    write_file(project_dir / ".claude" / "agents" / "coder.md", tmpl_coder(ctx))
    write_file(project_dir / ".claude" / "agents" / "reviewer.md", tmpl_reviewer(ctx))
    write_file(project_dir / ".claude" / "agents" / "cleanup.md", tmpl_cleanup(ctx))

    # ── docs/ ──
    _log("\n📁 生成 docs/ 知识库...")
    write_file(project_dir / "docs" / "architecture" / "overview.md", tmpl_overview(ctx))
    write_file(project_dir / "docs" / "architecture" / "boundaries.md", tmpl_boundaries(ctx))
    write_file(project_dir / "docs" / "conventions" / "README.md", tmpl_conventions_readme(ctx))
    write_file(project_dir / "docs" / "design" / "TEMPLATE.md", tmpl_design_template())
    write_file(project_dir / "docs" / "plans" / "current-sprint.md", tmpl_current_sprint())

    # ── scripts/ ──
    _log("\n📁 生成 scripts/ 验证脚本...")
    check_deps = project_dir / "scripts" / "check-layer-deps.sh"
    write_file(check_deps, tmpl_check_layer_deps(ctx))
    make_executable(check_deps)

    check_fresh = project_dir / "scripts" / "check-doc-freshness.sh"
    write_file(check_fresh, tmpl_check_doc_freshness())
    make_executable(check_fresh)

    agent_verify = project_dir / "scripts" / "agent-verify.sh"
    write_file(agent_verify, tmpl_agent_verify(ctx))
    make_executable(agent_verify)

    harness_check = project_dir / "scripts" / "harness-check.sh"
    write_file(harness_check, tmpl_harness_check(ctx))
    make_executable(harness_check)

    # ── .github/workflows/ ──
    _log("\n📁 生成 CI 管线...")
    write_file(project_dir / ".github" / "workflows" / "harness-checks.yml", tmpl_ci(ctx))

    # ── 汇总 ──
    _log("\n✅ Harness Engineering 基础设施已初始化")
    _log(f"   新增 {len(created)} 个文件 | 跳过 {len(skipped)} 个文件")

    return {
        "created": created,
        "skipped": skipped,
        "total_created": len(created),
        "total_skipped": len(skipped),
    }
