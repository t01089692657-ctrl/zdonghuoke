#!/usr/bin/env bash
# ZDHK 自动获客系统 —— Mac 一键启动（免 Docker 本地模式）
# 用法：解压后在项目根目录执行  bash mac-quickstart.sh
# 作用：装依赖 → 灌演示数据 → 同时启动后端(8000)与前端(3000)，Ctrl+C 一并停止。
set -euo pipefail
cd "$(dirname "$0")"

echo "==============================================="
echo "  ZDHK 自动获客系统 · Mac 本地启动"
echo "==============================================="

# ---- 0. 检查前置工具 --------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1; }

if ! need uv; then
  echo "❌ 未找到 uv（Python 包管理器）。安装："
  echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "   然后重开终端再运行本脚本。"
  exit 1
fi
if ! need pnpm; then
  echo "❌ 未找到 pnpm（前端包管理器）。安装（需先有 Node 18+，可用 brew install node）："
  echo "   npm install -g pnpm"
  echo "   或： brew install pnpm"
  exit 1
fi
echo "✅ uv 与 pnpm 已就绪"

# ---- 1. 后端依赖 + 演示数据 -------------------------------------------------
echo "--- [1/3] 安装后端依赖（uv sync）..."
( cd services/api && uv sync --extra dev >/dev/null )

echo "--- [2/3] 生成演示数据（本地 fake 模式，零外部调用）..."
( cd services/api && rm -f local.db && DATABASE_URL="sqlite+aiosqlite:///./local.db" ADAPTER_MODE=local uv run python -m app.scripts.seed )

# ---- 2. 前端依赖 ------------------------------------------------------------
echo "--- [3/3] 安装前端依赖（pnpm install，首次较慢）..."
( cd apps/web && pnpm install --silent )

# ---- 3. 启动 ----------------------------------------------------------------
echo "==============================================="
echo "  启动服务中... （Ctrl+C 停止全部）"
echo "==============================================="

pids=()
cleanup() { echo; echo "正在停止..."; for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; exit 0; }
trap cleanup INT TERM

( cd services/api && DATABASE_URL="sqlite+aiosqlite:///./local.db" ADAPTER_MODE=local \
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 ) &
pids+=($!)

( cd apps/web && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev ) &
pids+=($!)

sleep 3
echo
echo "  ✅ 后端 API :  http://localhost:8000/docs"
echo "  ✅ 前端界面 :  http://localhost:3000"
echo
echo "  演示已灌入 18 家公司数据，直接打开前端即可看到。"
echo "  （切换到真实供应商：编辑 .env 设 ADAPTER_MODE=cloud 并填密钥，见 infra/README.md）"
echo
wait
