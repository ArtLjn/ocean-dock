---
last_updated: 2026-05-09
status: active
---

# 模块边界与依赖规则

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

## 豁免机制

特殊情况下需绕过约束时，必须添加注释说明原因：

```python
# harness-exempt: 此处需要直接访问 repo 层，原因见 #PR-XXX
from app.repositories.user_repo import UserRepository
```
