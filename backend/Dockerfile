# Ruoxue Backend — Python FastAPI
# Multi-stage build for smaller image

FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
# 本地构建用清华源（实测 ~1s vs 官方源 15s+）; CI 通过 PIP_INDEX_URL 环境变量覆盖为官方源
RUN pip install --no-cache-dir --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

FROM python:3.12-slim
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy backend source code (kept as 'backend' package for imports)
COPY . ./backend/

# 注: skills/ 已迁移到仓库根目录（1213429 skills-kit 重构）,
# build context 是 backend/, 无法复制——容器内 skill 注入降级（聊天/Agent/RAG 不受影响）

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
