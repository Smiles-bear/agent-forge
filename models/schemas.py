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


# --- Agent schemas (四维能力向量) ---

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    tech_stack: list[str] = Field(..., min_length=1, description="技术栈，从受控词汇表选")
    task_types: list[str] = Field(..., min_length=1, description="任务类型，从受控词汇表选")
    domains: list[str] = Field(..., min_length=1, description="领域，从受控词汇表选")
    difficulty: str = Field(default="medium", description="难度: easy/medium/hard")
    endpoint: str = Field(..., description="Agent 调用地址")
    protocol: str = Field(default="http", description="http | mcp | grpc")
    input_schema: dict | None = None
    output_schema: dict | None = None
    tools: list[str] | None = None
    department: str = Field(default="uncategorized")
    capability_tags: list[str] | None = None
    verification: dict | None = Field(default=None, description="验证配置: type, test_cases, steps")


class AgentRegisterResponse(BaseModel):
    status: str
    agent_id: int | None = None
    name: str
    similarity: float | None = None
    closest_agent: str | None = None
    endpoint_reachable: bool | None = None
    message: str


class AgentResult(BaseModel):
    id: int
    name: str
    tech_stack: list[str] | None = None
    task_types: list[str] | None = None
    domains: list[str] | None = None
    difficulty: str | None = None
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
    tech_stack: list[str] | None = None
    task_types: list[str] | None = None
    domains: list[str] | None = None
    difficulty: str | None = None
    endpoint: str
    protocol: str
    input_schema: dict | None
    output_schema: dict | None
    tools: list[str] | None
    department: str
    capability_tags: list[str] | None
    verification_config: dict | None = None
    reliability_score: float | None = None
    avg_latency_ms: int | None = None
    total_calls: int = 0
    created_at: datetime | None = None


class AgentMatchRequest(BaseModel):
    task: str = Field(..., min_length=1, description="用户任务描述")
    top_k: int = Field(default=3)


class AgentMatchResult(BaseModel):
    agent: AgentResult
    tech_sim: float | None = None
    task_sim: float | None = None
    domain_sim: float | None = None
    diff_sim: float | None = None
    match_reason: str


class AgentMatchResponse(BaseModel):
    task: str
    project: str
    matches: list[AgentMatchResult]
    hint: str | None = None


class AgentExecuteRequest(BaseModel):
    task: str = Field(..., description="给 Agent 的任务")
    context: dict | None = Field(default=None)


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


# --- Verification schemas ---

class VerificationResultOut(BaseModel):
    id: int
    agent_id: int
    test_index: int
    step_scores: dict
    overall: float
    raw_output: str | None = None
    created_at: datetime | None = None


# --- Verification status schemas ---

class VerifyRequest(BaseModel):
    test_cases: list[dict] | None = Field(default=None, description="Optional: override existing test cases")


class VerifyResponse(BaseModel):
    status: str
    agent_id: int
    message: str


class VerificationStepResult(BaseModel):
    test_index: int
    overall: float
    steps: dict


class VerificationStatusResponse(BaseModel):
    agent_id: int
    reliability_score: float | None
    total_tests: int
    completed_tests: int
    status: str  # pending | in_progress | completed
    results: list[VerificationStepResult]
