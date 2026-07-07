# ZDHK 自动获客系统 —— 开发者命令入口
# Mac mini 上最常用：  make up   （一条命令启动全栈）
.DEFAULT_GOAL := help
.PHONY: help up down logs build dev-api dev-web install test test-api lint fmt seed clean

help: ## 显示所有命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## 用 docker compose 启动全栈（Postgres + API + Web）
	docker compose up --build

down: ## 停止并移除容器
	docker compose down

logs: ## 跟随查看容器日志
	docker compose logs -f

install: ## 安装后端(uv)与前端(pnpm)依赖，用于本地免 Docker 开发
	cd services/api && uv sync
	cd apps/web && pnpm install

dev-api: ## 本地免 Docker 启动后端（需先 make install，可配合 SQLite）
	cd services/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web: ## 本地免 Docker 启动前端
	cd apps/web && pnpm dev

test: test-api ## 运行所有测试

test-api: ## 运行后端测试
	cd services/api && uv run pytest -q

lint: ## 静态检查（ruff + mypy）
	cd services/api && uv run ruff check . && uv run mypy app

fmt: ## 格式化代码
	cd services/api && uv run ruff format . && uv run ruff check --fix .

seed: ## 灌入演示数据（本地 fake 模式）
	cd services/api && uv run python -m app.scripts.seed

clean: ## 清理本地缓存与本地库
	rm -rf services/api/local.db services/api/.pytest_cache services/api/.ruff_cache
