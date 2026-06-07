# Agent Platform Business Risks

## P0 — Fix Immediately

### 1. Capability Fraud
Agent declares capabilities at registration but cannot actually perform them. Current verification catches format errors (contract) and broken code (execute), but rubric scoring uses the same LLM that generated the output — self-grading is unreliable.

### 2. Execute Timeout Without Retry
Agent Ollama CPU inference times out and returns error directly. No retry, no graceful degradation, no circuit breaker.

### 3. Code Injection in Execute Verification
Verification execute type runs agent-generated code in subprocess. Protected only by temp directory isolation and timeout. No true sandbox (seccomp/container isolation).

### 4. No Re-verify Endpoint
Changing one line of system prompt required deleting and re-registering the agent. Fixed in this iteration.

### 5. Judge Bias
Rubric scoring uses the same qwen3:8b model as the agent being evaluated. RUBRIC_DOUBLE_CHECK mitigates slightly but root cause remains. Needs cross-model judging (e.g., GPT scoring Ollama output).

### 6. Zero-Match Silent Failure
When no agent matches a task (all dimension similarities low), returns empty list. User doesn't know whether to rephrase, register a new agent, or lower expectations.

---

## P1 — Fix Next Round

### 7. Endpoint Unreachable at Registration
No connectivity check at registration time. Failure discovered only at execute time.

### 8. False Positive Matching
High vector similarity but misaligned capability. Four-dimension search reduces but doesn't eliminate single-vector false positives.

### 9. LLM Ranking Instability
Same task matched twice may produce different rankings due to LLM temperature randomness. No reproducibility guarantee.

### 10. Multi-Candidate Selection Strategy
Three backend agents with reliability 0.8 / 0.6 / null. Which to choose? No explicit strategy.

### 11. Test Case Overfitting
Verification test cases hardcoded in docker-compose. Agents can optimize for known questions. Need dynamic question generation.

### 12. Unusable Output
Agent returns content but format is wrong or code doesn't run. No post-execution validation for actual usage.

### 13. Undetectable Partial Success
Code Reviewer finds 3 issues but misses the critical 4th. No detection mechanism.

### 14. Agent Mid-Task Crash
Ollama OOM, container crash, network disconnect. Execute path has no retry or recovery.

### 15. Output Inconsistency
Same code reviewed twice gets different results. LLM inherent randomness without consistency check.

### 16. Verification Environment Dependencies
Execute verification runs pip install in subprocess — network-dependent and slow. Needs pre-built base images.

### 17. Verification Staleness
Agent verified last week at 0.75. Model changed, Ollama version updated — is the score still valid? reliability_score doesn't auto-decay.

### 18. Label Drift
User selects `["python","fastapi"]` but actual agent capability is `["python","flask"]`. Labels ≠ capabilities.

### 19. Cold Start
New project has zero agents. First agent registered has no reference baseline.

---

## P2 — Platform Maturity

### 20. Agent Version Management
Same agent name has multiple versions in DB. Dedup relies on vector similarity, not version numbers. No way to know which is the latest.

### 21. Reliability Decay
Agent runs 100 tasks, reliability is still the registration score. No runtime feedback loop to update reliability.

### 22. Missing Audit Trail
Match routed task to Frontend Developer but why not Code Reviewer? Vector search intermediate scores not persisted. Match reason exists but not granular enough.

### 23. Observability Gap
Which agent is busiest? Slowest? Highest error rate? total_calls and avg_latency_ms recorded but no aggregation query or dashboard.

### 24. No Authentication
Anyone can register agents and call execute. No auth mechanism.

### 25. No Rate Limiting
Same agent matched 100 times, execute hammers Ollama. No rate limiting.

### 26. Registration Dedup Accuracy
Vector dedup threshold 0.95 has no data backing. Same-name different-version agents may be incorrectly rejected or accepted.

### 27. Cold Data Accumulation
Frequent agent updates produce stale verification_results. No cleanup or archival strategy.

---

## Priority Summary

| Priority | Count | Key Themes |
|----------|-------|-----------|
| P0 | 6 | Capability trust, safety, basic re-verify |
| P1 | 13 | Matching accuracy, verification reliability, operational resilience |
| P2 | 8 | Versioning, observability, security, data lifecycle |
