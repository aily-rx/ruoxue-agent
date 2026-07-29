.PHONY: help install dev lint lint-backend lint-frontend test test-backend test-frontend build docker-up docker-down clean

# Default target
help:
	@echo "Ruoxue - 可用命令："
	@echo ""
	@echo "  make install        安装前后端依赖"
	@echo "  make dev            启动开发环境（前后端同时运行）"
	@echo "  make lint           代码检查（ruff + eslint）"
	@echo "  make test           运行前后端测试"
	@echo "  make build          构建生产版本"
	@echo "  make docker-up      Docker 一键启动"
	@echo "  make docker-down    Docker 停止并清理"
	@echo "  make clean          清理缓存和构建产物"

# Install all dependencies
install:
	@echo "=== 安装后端依赖 ==="
	cd backend && pip install -r requirements.txt -r requirements-dev.txt
	@echo "=== 安装前端依赖 ==="
	cd frontend && npm install

# Start development servers
dev:
	@echo "=== 启动后端 (localhost:8000) ==="
	python -m backend.main &
	@echo "=== 启动前端 (localhost:5173) ==="
	cd frontend && npm run dev

# Lint all code
lint: lint-backend lint-frontend

lint-backend:
	@echo "=== Ruff 检查 ==="
	cd backend && ruff check .

lint-frontend:
	@echo "=== ESLint 检查 ==="
	cd frontend && npm run lint

# Run all tests
test: test-backend test-frontend

test-backend:
	@echo "=== Pytest ==="
	python -m pytest backend/tests/ -v --asyncio-mode=auto

test-frontend:
	@echo "=== Vitest ==="
	cd frontend && npm run test

# Production build
build:
	@echo "=== 前端构建 ==="
	cd frontend && npm run build

# Docker compose
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down --volumes

# Clean artifacts
clean:
	@echo "=== 清理缓存 ==="
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.vite 2>/dev/null || true
	@echo "Clean complete."