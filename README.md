# Skill Registry

AI Skill 注册平台——上传 SKILL.md → 向量去重检查 → 语义搜索。按 project 隔离，每个项目独立的向量空间。

## 为什么需要这个

写 Claude Code Skill 的人越来越多，时间长了会忘记写过什么、也容易写重复的 Skill。Skill Registry 是一个 **Skill 图书馆**——上传、搜索、查重，按项目分类管理。

## 快速开始

```bash
# 1. 启动数据库
docker compose up -d

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 4. 验证
curl http://localhost:8000/
```

## API 端点

### 上传 Skill

```bash
curl -X POST http://localhost:8000/api/v1/my-project/skills/upload \
  -H "Content-Type: text/plain" \
  -d '---
name: react-component
description: 创建 React 组件及其单元测试
version: "1.0.0"
---

# React Component Skill

详细的 skill 内容...
'
```

返回三种状态：

| 相似度 | 状态 | 行为 |
|--------|------|------|
| > 0.95 | `rejected` | 拒绝上传，返回最相似的 skill 名称 |
| 0.85 ~ 0.95 | `created_with_warning` | 入库但提醒可能冗余 |
| < 0.85 | `created` | 正常入库 |

### 搜索 Skill

```bash
curl "http://localhost:8000/api/v1/my-project/skills/search?q=react组件&top_k=5"
```

### 查看列表

```bash
curl http://localhost:8000/api/v1/my-project/skills
```

### 查看详情

```bash
curl http://localhost:8000/api/v1/my-project/skills/1
```

### 删除 Skill

```bash
curl -X DELETE http://localhost:8000/api/v1/my-project/skills/1
```

### 健康检查

```bash
# 全局统计
curl http://localhost:8000/api/v1/health

# 项目统计
curl http://localhost:8000/api/v1/my-project/health
```

## 完整端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/{project}/skills/upload` | 上传 SKILL.md（text/plain） |
| GET | `/api/v1/{project}/skills/search?q=&top_k=` | 语义搜索 |
| GET | `/api/v1/{project}/skills` | 技能列表 |
| GET | `/api/v1/{project}/skills/{id}` | 技能详情 |
| DELETE | `/api/v1/{project}/skills/{id}` | 删除技能 |
| GET | `/api/v1/{project}/health` | 项目统计 |
| GET | `/api/v1/health` | 全局统计 |

## 架构

```
POST /api/v1/{project}/skills/upload
  → services/parser.py        解析 YAML frontmatter
  → store/vector_store.py     encode description (512-dim)
  → store/db.py               pgvector cosine_distance 去重检查
  → services/skill_service.py 通过/警告/拒绝 三态返回

GET /api/v1/{project}/skills/search?q=
  → vector_store.encode(query)
  → pgvector cosine_distance TOP-K
  → 返回结果 + 相似度分数
```

## 技术栈

| 层 | 技术 |
|---|------|
| 框架 | FastAPI + Pydantic v2 |
| 数据库 | PostgreSQL 16 + pgvector |
| Embedding | BAAI/bge-small-zh-v1.5 (512 维, 单例模式) |
| 部署 | Docker Compose |

## 项目结构

```
skill-registry/
├── main.py                  # FastAPI 入口
├── config.py                # 配置（DB URL / 阈值 / 模型）
├── docker-compose.yml       # PostgreSQL + pgvector
├── routers/api.py           # 7 个端点
├── models/schemas.py        # Pydantic 模型
├── store/
│   ├── db.py                # SQLAlchemy ORM + 自动建表
│   └── vector_store.py      # Embedding + 余弦搜索
└── services/
    ├── parser.py             # SKILL.md YAML 解析
    └── skill_service.py      # 上传/搜索/去重 业务逻辑
```

## 配置

通过 `.env` 文件或环境变量：

```bash
DATABASE_URL=postgresql://kb_user:kb_pass@127.0.0.1:5433/skill_registry
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEDUP_HIGH_THRESHOLD` | 0.95 | 超过此值拒绝上传 |
| `DEDUP_WARN_THRESHOLD` | 0.85 | 超过此值警告 |
| `SEARCH_DEFAULT_TOP_K` | 10 | 默认返回条数 |
| `EMBEDDING_MODEL` | BAAI/bge-small-zh-v1.5 | 向量模型 |
