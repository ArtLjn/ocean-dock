#!/bin/bash
# scripts/check-layer-deps.sh
# 检查分层架构依赖方向，确保不违规

set -e

ERRORS=0
WARNINGS=0

# ── 后端检查 ──
BACKEND="backend/app"
if [ -d "$BACKEND" ]; then
  echo "🔍 检查后端分层依赖..."

  # api/ 层不能直接引用 repositories/
  if grep -rn "from.*repositories\|import.*repositories" "$BACKEND/api/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: api/ 层直接引用了 repositories/ 层"
    echo "✅ FIX: 通过 services/ 层访问数据，如 from app.services.xxx import XxxService"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # repositories/ 层不能引用 services/
  if grep -rn "from.*services\|import.*services" "$BACKEND/repositories/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: repositories/ 层反向引用了 services/ 层"
    echo "✅ FIX: 使用接口解耦，通过依赖注入获取 service"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # models/ 层不能引用 repositories/ 或 services/
  if grep -rn "from.*\(repositories\|services\)\|import.*\(repositories\|services\)" "$BACKEND/models/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: models/ 层引用了 repositories/ 或 services/ 层"
    echo "✅ FIX: models/ 是纯数据定义，不应依赖业务层"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
fi


# ── 前端检查 ──
FRONTEND="frontend/src"
if [ -d "$FRONTEND" ]; then
  echo "🔍 检查前端分层依赖..."

  # components/ 不能直接引用 services/
  if grep -rn "from.*services\|import.*services" "$FRONTEND/components/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: components/ 直接引用了 services/ 层"
    echo "✅ FIX: 在 app/ 页面层调用 services/，通过 props 传递数据给组件"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # lib/ 不能引用 services/
  if grep -rn "from.*services\|import.*services" "$FRONTEND/lib/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: lib/ 层引用了 services/ 层"
    echo "✅ FIX: lib/ 是基础设施层，不应依赖业务逻辑"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
fi

# ── 文件大小检查 ──
echo "🔍 检查文件大小..."

# Python 文件
for f in $(find backend/ -name "*.py" 2>/dev/null | grep -v __pycache__ | grep -v ".venv"); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 500 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 500）"
    echo "✅ FIX: 拆分为更小的模块，将辅助函数移至 utils/"
    ERRORS=$((ERRORS + 1))
  fi
done

# TypeScript 文件
for f in $(find frontend/src/ -name "*.ts" -o -name "*.tsx" 2>/dev/null | grep -v node_modules); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 300 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 300）"
    echo "✅ FIX: 拆分为更小的组件或模块"
    ERRORS=$((ERRORS + 1))
  fi
done

# ── TODO/FIXME 检查 ──
echo "🔍 检查 TODO/FIXME 残留..."
TODO_COUNT=$(grep -rn "TODO\|FIXME\|NotImplemented\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | wc -l | tr -d ' ')
if [ "$TODO_COUNT" -gt 0 ]; then
  echo "⚠️  发现 $TODO_COUNT 处 TODO/FIXME 残留："
  grep -rn "TODO\|FIXME\|NotImplemented\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | head -20
  WARNINGS=$((WARNINGS + 1))
fi

# ── 结果 ──
echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "❌ 架构检查失败：${ERRORS} 个错误，${WARNINGS} 个警告"
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "⚠️  架构检查通过但有 ${WARNINGS} 个警告"
  exit 0
fi

echo "✅ 架构依赖检查全部通过"
