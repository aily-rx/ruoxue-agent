# Ruoxue — 依赖清单

> 版本: v1.0 | 日期: 2026-07-24

---

## 前端

### Phase 1 依赖

```json
// frontend/package.json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^6.0.0"
  }
}
```

> Phase 1 极简：React + Vite + TypeScript，不需要额外库。
> SSE 用原生 `fetch` + `ReadableStream`，不需要 EventSource polyfill。

### Phase 2 追加

```
无额外 npm 依赖。
Web Audio API、getUserMedia 均为浏览器原生 API。
```

### Phase 3 追加

```
Live2D Cubism SDK for Web 5  (CDN 引入或 npm 包)
https://www.live2d.com/en/download/cubism-sdk/
```

---

## 后端

### Phase 1 依赖

```
# backend/requirements.txt
fastapi>=0.110
uvicorn[standard]>=0.30
langchain>=0.3
langchain-core>=0.3
langchain-openai>=0.2
pydantic>=2.0
httpx>=0.28
python-multipart>=0.0.9
```

### Phase 2 追加

```
edge-tts
sherpa-onnx
```

### Phase 3 追加

```
pypinyin>=0.50
```

### Phase 4 追加

```
langgraph>=0.2
chromadb>=0.5
faiss-cpu>=1.8
pypdf>=5.0
```

---

## 全局工具

```
uv / pip        Python 包管理
Node.js 20+     前端运行时
Git             版本管理
VS Code         推荐编辑器 (Ruff 插件)
```

---

*更新于 2026-07-24*

