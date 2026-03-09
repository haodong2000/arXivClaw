from __future__ import annotations

import json
import time

import httpx

from arxivclaw.models import Paper, ScoredPaper


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: int = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def score_paper(self, paper: Paper, keywords: list[str]) -> ScoredPaper:
        prompt = self._build_prompt(paper, keywords)
        data = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a strict paper relevance evaluator."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = self._post_with_retry(client=client, headers=headers, data=data)

        content = response.json()["choices"][0]["message"]["content"]
        parsed = self._safe_parse_json(content)

        return ScoredPaper(
            paper=paper,
            score=float(parsed.get("score", 0)),
            relevance=parsed.get("relevance", "unknown"),
            matched_keywords=parsed.get("matched_keywords", []),
            reasoning=parsed.get("reasoning", ""),
        )

    def _post_with_retry(self, client: httpx.Client, headers: dict, data: dict) -> httpx.Response:
        max_attempts = 4
        base_delay_seconds = 3.0

        last_exception: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.post(f"{self._base_url}/chat/completions", headers=headers, json=data)
                status = response.status_code
                if status in (429, 408, 500, 502, 503, 504) and attempt < max_attempts:
                    time.sleep(base_delay_seconds * (2 ** (attempt - 1)))
                    continue
                response.raise_for_status()
                return response
            except httpx.RequestError as exc:
                last_exception = exc
                if attempt >= max_attempts:
                    raise
                time.sleep(base_delay_seconds * (2 ** (attempt - 1)))

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("LLM request failed without a captured exception")

    @staticmethod
    def _build_prompt(paper: Paper, keywords: list[str]) -> str:
        keyword_text = ", ".join(keywords) if keywords else ""
        return (
            "Evaluate relevance of an arXiv paper based only on provided keywords and title. "
            "Do not use abstract, authors, or categories for scoring. "
            "Return valid JSON only with keys: score (0-100), relevance, matched_keywords (array), reasoning.\n\n"
            f"Keywords: {keyword_text}\n"
            f"Title: {paper.title}\n"
        )

    @staticmethod
    def _safe_parse_json(raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"score": 0, "relevance": "unknown", "matched_keywords": [], "reasoning": raw[:300]}
