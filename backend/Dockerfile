# Ruoxue Backend — Python FastAPI
# Multi-stage build for smaller image

FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
# 国内环境 pypi 直连超时, 用清华镜像（CI 的 GitHub runner 亦可访问）
RUN pip install --no-cache-dir --user -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy DeepSeek Skills (dynamic prompt injection for agent_graph.py)
COPY deepseek-skills/ ./deepseek-skills/

# Copy backend source code (kept as 'backend' package for imports)
COPY . ./backend/

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
