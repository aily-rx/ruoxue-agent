# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] — 2026-07-29

### Added
- DeepSeek Skills 技能库：11 个 AI 编程技能（verify / read-before-code / prototype-first / defensive-output / diagnose-bugs / implement / code-review / tdd / codebase-design / grill-me / handoff）
- agent_graph.py 第四层 prompt（skill_context），基于关键词动态匹配并注入技能指令
- skill_loader.py 通用加载器，零依赖
- 企业级工程化：ruff/mypy/pytest + eslint/vitest
- Docker 容器化：前后端独立镜像 + docker-compose 编排
- GitHub Actions CI/CD：lint → test → build & push to GHCR
- Makefile 快捷命令
- 结构化 JSON 日志（config.setup_logging）
- pre-commit / pre-push 两层 hook

### Changed
- deepseek-skills/ 移入 backend/ 目录
- Docker 前后端独立构建上下文

### Fixed
- Makefile `test-backend` 改为从 backend/ 目录运行 pytest
- ruff per-file-ignores 增加 agent_graph.py（E402）
- README 启动命令路径修正

## [0.3.1] — 2026-07-30

### Changed
- TTS 切换为 Edge TTS (29 个神经语音, 主力) + pyttsx3/SAPI5 (离线自动兜底)
- Skill 系统重构：skills-kit/ 套装 + init.sh 一键安装 + CORE_RULES 写入 CLAUDE.md 硬约束
- skill_loader.py 移入 backend/agent/，skills/ 提到项目根目录
- 删除 backend/deepseek-skills/（被 skills-kit/ 替代）
- README / CHANGELOG / docs/project-structure.md 更新至最新结构

### Fixed
- TTS 挂死：pyttsx3 线程池加 COM 初始化 + 60s 超时保护
- 口型不同步：Edge TTS WordBoundary 参数漏传 + char_durations 对齐修复
- SSE 竞态：ChatPanel 恢复 pendingRef 缓冲区机制

## [0.1.0] — 2026-07-25

### Added
- Phase 1: SSE 流式文字对话 + 情绪标签 + 会话记忆
- Phase 2: SenseVoice ASR 语音识别 + Edge TTS 合成 + 口型同步
- Phase 3: Live2D 数字人渲染 + 情绪驱动 + Motion 语境绑定
- Phase 4: LangGraph Agent + 5 工具 + Chroma 长期记忆 + FAISS RAG
