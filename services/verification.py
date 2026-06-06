import json
import logging
import tempfile
import subprocess
import os
import re
import httpx
from sqlalchemy import text
from store.db import SessionLocal, Agent, VerificationResult
from config import VERIFICATION_TIMEOUT, RUBRIC_MODEL, RUBRIC_DOUBLE_CHECK

logger = logging.getLogger(__name__)


async def run_verification(agent_id: int, config: dict, endpoint: str):
    """异步验证入口。由 router 的 BackgroundTasks 触发。"""
    session = SessionLocal()
    try:
        test_cases = config.get("test_cases", [])
        all_scores = []

        for i, tc in enumerate(test_cases):
            # 1. 调用 Agent /run
            output = await _call_agent(endpoint, tc["task"], tc.get("context"))
            if output is None:
                _save_result(session, agent_id, i, {"error": "agent call failed"}, 0.0, "")
                all_scores.append(0.0)
                continue

            # 2. 逐 step 打分
            step_scores = {}
            for step in tc.get("steps", []):
                step_type = step.get("type")
                if step_type == "contract":
                    score = _check_contract(output, step.get("required_keys", []))
                    step_scores["contract"] = score
                elif step_type == "execute":
                    score = await _run_execute(output, step)
                    step_scores["execute"] = score
                elif step_type == "rubric":
                    score = await _llm_rubric(output, tc["task"], step.get("dimensions", {}))
                    step_scores["rubric"] = score

            overall = round(min(step_scores.values()), 4) if step_scores else 0.0
            _save_result(session, agent_id, i, step_scores, overall, output)
            all_scores.append(overall)
            logger.info("Agent %d test %d: steps=%s overall=%.4f", agent_id, i, step_scores, overall)

        # 3. 计算并更新 reliability_score
        reliability = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.reliability_score = reliability
            if agent.verification_config:
                try:
                    vconfig = json.loads(agent.verification_config) if isinstance(agent.verification_config, str) else agent.verification_config
                    vconfig["_last_result"] = reliability
                    agent.verification_config = json.dumps(vconfig, ensure_ascii=False)
                except Exception:
                    pass
            session.commit()
            logger.info("Agent %d reliability_score = %.4f", agent_id, reliability)

    except Exception as e:
        logger.error("Verification failed for agent %d: %s", agent_id, e)
    finally:
        session.close()


async def _call_agent(endpoint: str, task: str, context: dict | None) -> str | None:
    """POST /run 到 Agent，返回原始响应文本。"""
    payload = {"task": task}
    if context:
        payload["context"] = context
    try:
        async with httpx.AsyncClient(timeout=VERIFICATION_TIMEOUT) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", resp.text)
    except Exception as e:
        logger.warning("Agent call failed: %s -> %s", endpoint, e)
        return None


def _check_contract(output: str, required_keys: list[str]) -> float:
    """检查输出 JSON 是否包含所有 required_keys。"""
    try:
        data = json.loads(output) if isinstance(output, str) else output
    except (json.JSONDecodeError, TypeError):
        match = re.search(r'\{[\s\S]*\}', output)
        if match:
            try:
                data = json.loads(match.group())
            except Exception:
                return 0.0
        else:
            return 0.0
    if not isinstance(data, dict):
        return 0.0
    missing = [k for k in required_keys if k not in data]
    return 0.0 if missing else 1.0


async def _run_execute(output: str, config: dict) -> float:
    """将 Agent 输出写入临时文件，执行 run_command，检查 exit_code。"""
    run_cmd = config.get("run_command", "")
    timeout = config.get("timeout", 30)
    assertions = config.get("assert", {})

    code = _extract_code(output)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = config.get("filename", "test_output.py")
            fpath = os.path.join(tmpdir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                run_cmd, shell=True, cwd=tmpdir,
                capture_output=True, text=True, timeout=timeout,
            )

            expected_exit = assertions.get("exit_code", 0)
            if result.returncode != expected_exit:
                logger.info("Execute exit_code mismatch: got %d, expected %d",
                            result.returncode, expected_exit)
                return 0.0
            return 1.0
    except subprocess.TimeoutExpired:
        logger.warning("Execute timeout after %ds", timeout)
        return 0.0
    except Exception as e:
        logger.warning("Execute failed: %s", e)
        return 0.0


def _extract_code(output: str) -> str:
    """从 Agent 输出中提取代码块。"""
    match = re.search(r'```(?:python)?\s*\n([\s\S]*?)\n```', output)
    if match:
        return match.group(1)
    match = re.search(r'```\s*\n([\s\S]*?)\n```', output)
    if match:
        return match.group(1)
    return output


async def _llm_rubric(output: str, task: str, dimensions: dict) -> float:
    """LLM 按量规打分。如果 RUBRIC_DOUBLE_CHECK，双评取低分。"""
    score1 = await _rubric_once(output, task, dimensions)
    if RUBRIC_DOUBLE_CHECK:
        score2 = await _rubric_once(output, task, dimensions)
        return round(min(score1, score2), 4)
    return score1


async def _rubric_once(output: str, task: str, dimensions: dict) -> float:
    """单次 LLM 量规评分。"""
    dim_text = "\n".join([f"- {name}: {desc}" for name, desc in dimensions.items()])

    prompt = f"""你是一个严厉的代码审查评分员。你的职责是找问题，不是表扬。

任务: {task}

评分维度:
{dim_text}

Agent 的回复:
---
{output[:2000]}
---

请对每个维度按 1-5 分打分，只返回 JSON，不要解释。
格式: {{"正确性": 4, "完整性": 3, "可操作性": 5}}
最低给 1 分，只给满分当你确信完美无缺。"""

    try:
        import ollama
        resp = ollama.chat(
            model=RUBRIC_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        content = resp["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 1 and lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
            else:
                content = "\n".join(lines[1:])
        scores = json.loads(content)

        if not isinstance(scores, dict):
            return 0.0

        normalized = []
        for name in dimensions.keys():
            raw = scores.get(name, 1)
            normalized.append(max(0.0, min(1.0, (raw - 1) / 4.0)))
        return round(sum(normalized) / len(normalized), 4) if normalized else 0.0
    except Exception as e:
        logger.warning("Rubric scoring failed: %s", e)
        return 0.5


def _save_result(session, agent_id: int, test_index: int,
                 step_scores: dict, overall: float, raw_output: str):
    """写入 verification_results 表。"""
    vr = VerificationResult(
        agent_id=agent_id,
        test_index=test_index,
        step_scores=json.dumps(step_scores, ensure_ascii=False),
        overall=overall,
        raw_output=raw_output[:5000] if raw_output else "",
    )
    session.add(vr)
    session.commit()
