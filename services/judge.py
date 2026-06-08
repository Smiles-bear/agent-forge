"""Multi-model judge framework for rubric scoring.

Pluggable judges — currently Ollama, GPT slot reserved.
Each judge takes (output, task, dimensions) → returns float 0-1.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


class BaseJudge:
    name: str = "base"

    def score(self, output: str, task: str, dimensions: dict) -> float:
        raise NotImplementedError


class OllamaJudge(BaseJudge):
    name = "ollama"

    def __init__(self, model: str = "qwen3:8b", host: str = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

    def score(self, output: str, task: str, dimensions: dict) -> float:
        import ollama

        dim_text = "\n".join([f"- {name}: {desc}" for name, desc in dimensions.items()])

        prompt = f"""You are a strict code review grader. Your job is to find problems, not praise.

Task: {task}

Scoring dimensions:
{dim_text}

Agent response:
---
{output[:2000]}
---

Score each dimension from 1-5. Return ONLY a JSON object, no explanation.
Format: {{"accuracy": 4, "completeness": 3, "actionability": 5}}
Give the minimum score of 1 unless you are certain it is perfect."""

        try:
            resp = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}], stream=False)
            content = resp["message"]["content"].strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else content
            scores = json.loads(content)

            if not isinstance(scores, dict):
                return 0.0

            normalized = []
            for name in dimensions.keys():
                raw = scores.get(name, 1)
                normalized.append(max(0.0, min(1.0, (raw - 1) / 4.0)))
            return round(sum(normalized) / len(normalized), 4) if normalized else 0.0
        except Exception as e:
            logger.warning("Ollama judge failed: %s", e)
            return 0.5


class GPTJudge(BaseJudge):
    name = "gpt"

    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def score(self, output: str, task: str, dimensions: dict) -> float:
        if not self.api_key:
            logger.warning("GPT judge unavailable: OPENAI_API_KEY not set")
            return self._fallback_ollama(output, task, dimensions)

        import httpx
        dim_text = "\n".join([f"- {name}: {desc}" for name, desc in dimensions.items()])

        prompt = f"""You are a strict code review grader. Score this agent response.

Task: {task}
Dimensions:
{dim_text}
Agent response:
---
{output[:2000]}
---
Score each dimension 1-5. Return ONLY JSON: {{"accuracy":4,"completeness":3,...}}"""

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.0},
                timeout=30,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            scores = json.loads(content)
            normalized = []
            for name in dimensions.keys():
                raw = scores.get(name, 1)
                normalized.append(max(0.0, min(1.0, (raw - 1) / 4.0)))
            return round(sum(normalized) / len(normalized), 4) if normalized else 0.0
        except Exception as e:
            logger.warning("GPT judge failed, falling back to Ollama: %s", e)
            return self._fallback_ollama(output, task, dimensions)

    def _fallback_ollama(self, output: str, task: str, dimensions: dict) -> float:
        return OllamaJudge().score(output, task, dimensions)


# ── Judge Registry ──

_judges = {}


def register_judge(judge: BaseJudge):
    _judges[judge.name] = judge
    logger.info("Registered judge: %s", judge.name)


def get_judges() -> list[BaseJudge]:
    return list(_judges.values())


def score_with_judges(output: str, task: str, dimensions: dict,
                      judge_names: list[str] = None) -> float:
    """Score with one or more judges. If multiple, take the minimum (strictest)."""
    judges = [_judges[n] for n in (judge_names or ["ollama"]) if n in _judges]
    if not judges:
        judges = [_judges.get("ollama", OllamaJudge())]

    scores = [j.score(output, task, dimensions) for j in judges]
    return round(min(scores), 4)


# Auto-register default judges
register_judge(OllamaJudge())
register_judge(GPTJudge())  # GPT waits for API key
