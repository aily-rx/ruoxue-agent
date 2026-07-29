# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] — 2026-07-29

### Added
- DeepSeek Skills 技能库：10 个 AI 编程技能（read-before-code / prototype-first / defensive-output / diagnose-bugs / implement / code-review / tdd / codebase-design / grill-me / handoff）
- agent_graph.py 第四层 prompt（skill_context），基于关键词动态匹配并注入技能指令
- skill_loader.py 通用加载器，零依赖，拷贝到任意项目即可用

### Changed
- Docker 企业化重构：前后端独立构建上下文（`context: ./backend` / `context: ./frontend`）
- deepseek-skills/ 移入 backend/ 目录，随 Dockerfile 打包进镜像
- CI/CD 同步更新 Docker 上下文路径

### Fixed
- Makefile `test-backend` 改为从 backend/ 目录运行 pytest
- ruff per-file-ignores 增加 agent_graph.py（E402）

### Added
- 企业级工程化改造：添加 ruff/mypy/pytest (后端) + eslint/prettier/vitest (前端)
- Docker 容器化：后端 Python 镜像 + 前端 Nginx 镜像 + docker-compose 编排
- GitHub Actions CI/CD：lint → test → build & push to GHCR
- Makefile 快捷命令（make install / lint / test / docker-up）
- 结构化 JSON 日志（config.setup_logging）
- pre-commit 钩子配置

### Fixed
- README 启动命令路径修正（必须从项目根目录运行 `python -m backend.main`）

## [0.1.0] — 2026-07-25

### Added
- Phase 1: SSE 流式文字对话 + 情绪标签 + 会话记忆
- Phase 2: SenseVoice ASR 语音识别 + Edge TTS 合成 + 口型同步
- Phase 3: Live2D 数字人渲染 + 情绪驱动 + Motion 语境绑定
- Phase 4: LangGraph Agent + 5 工具 + Chroma 长期记忆 + FAISS RAG
