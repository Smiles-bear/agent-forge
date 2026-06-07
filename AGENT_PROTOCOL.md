# AgentForge Agent Protocol v1.0

Standard interface for agents to register and execute on the AgentForge platform.

## Endpoints

### GET /health

Health check. Called at registration and periodically by the platform.

**Response (200):**
```json
{
  "status": "ok",
  "agent": "string — agent name"
}
```

### POST /run

Execute a task.

**Request:**
```json
{
  "task": "string — the task description",
  "context": {
    "code": "optional code snippet",
    "...": "any additional context"
  }
}
```

**Response (200):**
```json
{
  "agent": "string — agent name",
  "result": "string — the output or response"
}
```

## Protocol Version

Include in registration payload:
```json
{
  "protocol_version": "1.0"
}
```

## Verification

At registration, the platform validates protocol compliance:
1. `GET /health` returns 200 with `{"status": "ok"}`
2. `POST /run` accepts `{"task": "...", "context": {...}}` and returns 200 with `{"agent": "...", "result": "..."}`

## Reference Implementation

See `agents/main.py` for the reference Python/FastAPI implementation.
