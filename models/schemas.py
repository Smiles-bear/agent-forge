from pydantic import BaseModel, Field
from datetime import datetime


class SkillResult(BaseModel):
    id: int
    name: str
    description: str
    author: str | None = "unknown"
    version: str | None = "1.0.0"
    similarity: float | None = None
    created_at: datetime | None = None


class SkillDetail(BaseModel):
    id: int
    project: str
    name: str
    description: str
    author: str | None
    version: str | None
    skill_content: str
    created_at: datetime | None


class SkillUploadResponse(BaseModel):
    status: str
    skill_id: int | None = None
    name: str
    similarity: float | None = None
    closest_name: str | None = None
    message: str


class SkillSearchResponse(BaseModel):
    query: str
    project: str
    results: list[SkillResult]


class SkillListResponse(BaseModel):
    project: str
    total: int
    skills: list[SkillResult]


class DeleteResponse(BaseModel):
    status: str
    skill_id: int


class HealthResponse(BaseModel):
    status: str
    skill_count: int
    embedding_model: str


# --- Agent schemas ---

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, description="能力描述，用于 embedding 和匹配")
    endpoint: str = Field(..., description="Agent 服务的调用地址")
    protocol: str = Field(default="http", description="http | mcp | grpc")
    input_schema: dict | None = None
    output_schema: dict | None = None
    tools: list[str] | None = None
    department: str = Field(default="uncategorized", description="所属部门")
    capability_tags: list[str] | None = None


class AgentRegisterResponse(BaseModel):
    status: str
    agent_id: int | None = None
    name: str
    similarity: float | None = None
    closest_agent: str | None = None
    message: str


class AgentResult(BaseModel):
    id: int
    name: str
    description: str
    department: str
    protocol: str
    capability_tags: list[str] | None = None
    reliability_score: float | None = None
    similarity: float | None = None
    created_at: datetime | None = None


class AgentDetail(BaseModel):
    id: int
    project: str
    name: str
    description: str
    endpoint: str
    protocol: str
    input_schema: dict | None
    output_schema: dict | None
    tools: list[str] | None
    department: str
    capability_tags: list[str] | None
    reliability_score: float | None
    avg_latency_ms: int | None
    total_calls: int
    created_at: datetime | None


class AgentMatchRequest(BaseModel):
    task: str = Field(..., min_length=1, description="用户的任务描述")
    top_k: int = Field(default=3)


class AgentMatchResult(BaseModel):
    agent: AgentResult
    match_reason: str


class AgentMatchResponse(BaseModel):
    task: str
    project: str
    matches: list[AgentMatchResult]


class AgentExecuteRequest(BaseModel):
    task: str = Field(..., description="给这个 Agent 的任务")
    context: dict | None = Field(default=None, description="额外的上下文参数")


class AgentExecuteResponse(BaseModel):
    agent_id: int
    agent_name: str
    task: str
    result: str
    latency_ms: int


class AgentListResponse(BaseModel):
    project: str
    total: int
    agents: list[AgentResult]


class AgentDeleteResponse(BaseModel):
    status: str
    agent_id: int
