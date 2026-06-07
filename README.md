# AgentForge

Multi-agent platform — register, match, execute, and verify AI agents.

## What It Does

```
Register → 4-Dim Capability Vector → Match → Execute → Verify → Reliability Score
```

- **Register**: Agents declare capabilities across 4 dimensions (tech_stack, task_types, domains, difficulty)
- **Match**: Vector search across 4 dimensions + LLM rerank
- **Execute**: HTTP forward to agent endpoints
- **Verify**: Automated testing (contract check / code execution / LLM rubric)
- **Skill Library**: Upload SKILL.md → dedup → semantic search

## Architecture

```
docker-compose (6 services)
├── db              (5433) — PostgreSQL + pgvector
├── registry        (8000) — FastAPI — core platform
├── code-reviewer   (8001) — Security & quality reviews
├── test-writer     (8002) — Pytest generation
├── backend-dev     (8003) — API & database design
└── frontend-dev    (8004) — React component development
```

## Quick Start

```bash
# Prerequisites: Docker + Ollama running on host
docker compose up -d --build

# Agents auto-register and verification runs automatically
# Check results after ~3 min
curl http://localhost:8000/api/v1/it-department/agents
```

## API Endpoints

### Agent Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/{project}/agents/register` | Register agent with 4-dim capability tags |
| POST | `/api/v1/{project}/agents/match` | Match task to best agent |
| POST | `/api/v1/{project}/agents/{id}/execute` | Execute task via agent |
| GET | `/api/v1/{project}/agents` | List all agents |
| GET | `/api/v1/{project}/agents/{id}` | Agent detail |
| DELETE | `/api/v1/{project}/agents/{id}` | Remove agent |
| GET | `/api/v1/{project}/departments` | Department summary |
| POST | `/api/v1/{project}/agents/{id}/verify` | Re-verify agent |
| GET | `/api/v1/{project}/agents/{id}/verification` | Verification status & results |

### Skill Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/{project}/skills/upload` | Upload SKILL.md |
| GET | `/api/v1/{project}/skills/search?q=` | Semantic search |
| GET | `/api/v1/{project}/skills` | List skills |
| GET | `/api/v1/{project}/skills/{id}` | Skill detail |
| DELETE | `/api/v1/{project}/skills/{id}` | Delete skill |

## Verification System

Three scoring methods:

| Type | How | Best For |
|------|-----|----------|
| `contract` | Validates JSON output has required keys | Any structured output |
| `execute` | Runs code in subprocess, checks exit code | Test Writer, Backend Dev |
| `rubric` | LLM scores output against dimension criteria | Code Reviewer, Frontend Dev |

Each agent runs 3 test cases at registration. Score = min(step scores) averaged across tests. Updated as `reliability_score` on the agent.

## Tech Stack

| Layer | Tech |
|-------|------|
| Framework | FastAPI + Pydantic v2 |
| Database | PostgreSQL + pgvector |
| Embedding | BAAI/bge-small-zh-v1.5 (512-dim) |
| LLM | Ollama (qwen3:8b) |
| Agents | Docker FastAPI services, env-var driven |
| Verification | contract / execute (subprocess) / rubric (LLM) |

## Business Risks

See [docs/business-risks.md](docs/business-risks.md) for 27 identified risks (P0/P1/P2).

## License

MIT
