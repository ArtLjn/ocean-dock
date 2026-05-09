---
last_updated: 2026-05-09
status: active
---

# 系统架构

## 后端分层

```
backend/app/
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


## 前端分层

```
frontend/src/
├── types/           # 纯类型定义，不依赖任何层
├── lib/             # 工具函数和基础设施，只依赖 types/
├── services/        # 业务逻辑，依赖 types/ 和 lib/
├── components/      # UI 组件，只依赖 types/ 和 lib/providers
└── app/             # 页面路由，可依赖所有层
```

## 核心约定

- 横切关注点（auth/log/telemetry）通过依赖注入，不被业务层直接 import
- API 版本统一 v1，路径前缀 `/api/v1/`
- 数据库迁移只用 alembic，禁止手动改表
