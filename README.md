# 🌸 Ruoxue — 多模态 AI Agent 数字人助手

一个住在你电脑里的 AI 数字人助手：能聊、能听、能说、能动、能用工具、能记事情。

## 项目介绍

### 她是什么？

Ruoxue（若雪）是一个住在你电脑里的 **AI 数字人助手**——不是冷冰冰的聊天框，而是一位看得见、听得懂、会说话、有表情的虚拟伙伴：

- **能聊** — 流式实时对话，回复逐字显示，带情绪有温度
- **能听** — 按住说话，她就能听懂你说了什么
- **能说** — 用自然的中文语音回答你，口型同步对得上
- **能动** — Live2D 形象有表情、会眨眼，说话时嘴巴会动，配合语气做动作
- **能帮忙** — 上网搜索、查天气、读取你电脑里的文件
- **能记住** — 记得你们聊过什么，还会基于你提供的文档回答问题

### 主要功能

| 功能 | 说明 |
|------|------|
| 💬 文字聊天 | 实时流式对话，情绪感知（开心、难过、惊讶、思考...8 种情绪） |
| 🎤 语音对话 | 按住说话即可对话，支持中文语音识别与合成 |
| 👧 Live2D 数字人 | 会眨眼、有表情、口型同步，配合对话内容做动作 |
| 🌐 联网搜索 | 实时搜索最新信息，不用自己开浏览器 |
| 🌦️ 天气查询 | 直接问"今天天气怎么样？" |
| 📄 文件阅读 | 可以读取你指定的本地文本 / PDF 文档 |
| 📚 私人知识库 | 放入你的文档，她就能基于这些内容回答问题 |

### 隐私与本地化

语音识别、语音合成、数字人动画、知识库检索全部在**本地运行**，无需上传音频或文档。只有文字回复需要调用 DeepSeek AI 服务（需配置 API Key）。

## Docker 部署

### 1. 前提条件

- 安装 Docker 与 Docker Compose（国内网络无需代理，镜像源已内置）
- DeepSeek API Key（注册即送免费额度）

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（必填）
# 可选：TAVILY_API_KEY（联网搜索用。不填走匿名额度（有速率限制）；
#       填自己的免费 Key 每月 1000 次额度，注册：https://tavily.com）
```

> `.env` 必须放在**项目根目录**（Docker Compose 与后端都从根目录读取）。

### 3. 启动

```bash
docker compose up -d --build
```

启动后：

- 前端界面：http://localhost
- 后端 API：http://localhost:8000 （Swagger 文档：http://localhost:8000/docs）
- 健康检查：`curl http://localhost:8000/api/health` → `{"status":"ok","llm_available":true,...}`

### 4. 常用命令

```bash
docker compose logs -f backend   # 跟踪后端日志
docker compose logs -f frontend  # 跟踪前端日志
docker compose down              # 停止（--volumes 才删除数据卷）
docker compose config            # 校验配置
```

### 5. 数据与模型（挂载目录，直接替换宿主机文件即可）

| 目录 | 用途 |
|---|---|
| `model_assets/` | 本地模型（ASR 语音识别等），只读挂载 |
| `skills/` | 技能库文件，只读挂载 |
| `chroma_data/` | 长期记忆数据 |
| `faiss_data/` | 知识库索引数据 |

> 代码修改后执行 `docker compose up -d --build` 增量重建即可生效（秒级）。
