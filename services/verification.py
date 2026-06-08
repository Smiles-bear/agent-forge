import json
import logging
import tempfile
import subprocess
import os
import asyncio
import re
from datetime import datetime, timezone
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
            agent.verified_at = datetime.now(timezone.utc)
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
    """Check if output contains all required_keys in a JSON object."""
    data = _extract_json(output)
    if data is None:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    missing = [k for k in required_keys if k not in data]
    return 0.0 if missing else 1.0


def _extract_json(output: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from output."""
    if not output:
        return None

    # 1. Direct parse
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Extract from ```json code block
    match = re.search(r'```json\s*\n([\s\S]*?)\n```', output)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Find balanced JSON object
    start = output.find('{')
    if start >= 0:
        string_val = False
        in_str = False
        for end in range(start, len(output)):
            ch = output[end]
            if in_str:
                if ch == '\\':
                    string_val = not string_val
                elif ch == '"' and not string_val:
                    in_str = False
                string_val = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '}' and end > start:
                    try:
                        return json.loads(output[start:end + 1])
                    except (json.JSONDecodeError, TypeError):
                        continue

    return None


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
    """Multi-judge rubric scoring. Uses all available judges, takes the minimum score."""
    from services.judge import get_judges

    loop = asyncio.get_event_loop()
    judges = get_judges()

    async def _score_one(judge):
        return await loop.run_in_executor(None, judge.score, output, task, dimensions)

    scores = []
    for j in judges:
        try:
            s = await asyncio.wait_for(_score_one(j), timeout=VERIFICATION_TIMEOUT)
            scores.append(s)
        except Exception as e:
            logger.warning("Judge %s failed: %s", j.name, e)

    if not scores:
        return 0.5
    # Take minimum across all judges (strictest)
    return round(min(scores), 4)


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


def get_verification_status(agent_id: int) -> dict | None:
    """Query verification progress and results for an agent."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return None

        results = (
            session.query(VerificationResult)
            .filter(VerificationResult.agent_id == agent_id)
            .order_by(VerificationResult.test_index)
            .all()
        )

        # Parse total_tests from verification_config
        total_tests = 0
        if agent.verification_config:
            try:
                vconfig = json.loads(agent.verification_config) if isinstance(agent.verification_config, str) else agent.verification_config
                total_tests = len(vconfig.get("test_cases", []))
            except Exception:
                pass

        completed = len(results)
        if agent.reliability_score is not None and completed >= total_tests and total_tests > 0:
            status = "completed"
        elif completed > 0:
            status = "in_progress"
        else:
            status = "pending"

        return {
            "agent_id": agent_id,
            "reliability_score": agent.reliability_score,
            "total_tests": total_tests,
            "completed_tests": completed,
            "status": status,
            "results": [
                {
                    "test_index": v.test_index,
                    "overall": v.overall,
                    "steps": json.loads(v.step_scores) if isinstance(v.step_scores, str) else v.step_scores,
                }
                for v in results
            ],
        }
    finally:
        session.close()


def clear_verification_results(agent_id: int):
    """Clear old verification results and reset reliability_score for an agent."""
    session = SessionLocal()
    try:
        session.query(VerificationResult).filter(
            VerificationResult.agent_id == agent_id
        ).delete()
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.reliability_score = None
        session.commit()
    finally:
        session.close()
