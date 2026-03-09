from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
import uuid

from arxivclaw.clients.arxiv_client import ArxivClient
from arxivclaw.clients.email_client import EmailClient
from arxivclaw.clients.llm_client import LLMClient
from arxivclaw.config import Settings
from arxivclaw.models import Paper, ScoredPaper
from arxivclaw.storage.state_store import StateStore

logger = logging.getLogger(__name__)


class RecommenderPipeline:
    def __init__(
        self,
        settings: Settings,
        arxiv_client: ArxivClient,
        llm_client: LLMClient,
        email_client: EmailClient,
        state_store: StateStore,
    ) -> None:
        self.settings = settings
        self.arxiv_client = arxiv_client
        self.llm_client = llm_client
        self.email_client = email_client
        self.state_store = state_store

    def run_once(self) -> dict:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        use_state_db = not self.settings.run_once
        if use_state_db:
            self.state_store.create_run(run_id)
        else:
            logger.info("RUN_ONCE mode: state.db is ignored (no dedup and no run persistence)")
        total_fetched = 0
        total_scored = 0
        total_sent = 0

        try:
            papers = self.arxiv_client.fetch_papers(
                query=self.settings.arxiv_query,
                max_results=self.settings.arxiv_max_results,
            )
            total_fetched = len(papers)
            logger.info("Fetched %d papers from arXiv", total_fetched)
            if self.settings.run_once:
                for idx, paper in enumerate(papers, start=1):
                    logger.debug("[Fetched %03d] %s | %s | %s", idx, paper.arxiv_id, paper.title, paper.link)

            if use_state_db:
                unprocessed = [paper for paper in papers if not self.state_store.is_processed(paper.arxiv_id)]
            else:
                unprocessed = papers
            logger.info("Unprocessed papers: %d", len(unprocessed))

            scored = self._score_papers(unprocessed)
            total_scored = len(scored)

            selected = self._select_top(scored)
            total_sent = len(selected)

            if selected:
                self.email_client.send_digest(selected, total_fetched=total_fetched)
                logger.info("Digest email sent with %d papers", len(selected))
            else:
                logger.info("No paper selected for digest")

            if use_state_db:
                self.state_store.mark_processed_many([paper.arxiv_id for paper in unprocessed])
                self.state_store.finish_run(
                    run_id,
                    status="success",
                    total_fetched=total_fetched,
                    total_scored=total_scored,
                    total_sent=total_sent,
                )
            return {
                "run_id": run_id,
                "status": "success",
                "fetched": total_fetched,
                "scored": total_scored,
                "sent": total_sent,
            }
        except Exception as exc:
            logger.exception("Pipeline run failed: %s", exc)
            if use_state_db:
                self.state_store.finish_run(
                    run_id,
                    status="failed",
                    total_fetched=total_fetched,
                    total_scored=total_scored,
                    total_sent=total_sent,
                    note=str(exc)[:500],
                )
            raise

    def _score_papers(self, papers: list[Paper]) -> list[ScoredPaper]:
        results: list[ScoredPaper] = []
        keywords = self.settings.keyword_list
        interval = max(self.settings.llm_request_interval_seconds, 0.0)
        for index, paper in enumerate(papers):
            try:
                scored = self.llm_client.score_paper(paper=paper, keywords=keywords)
                if self.settings.run_once:
                    logger.debug(
                        "[Scored] %s | score=%.1f | relevance=%s | matched=%s | title=%s",
                        paper.arxiv_id,
                        scored.score,
                        scored.relevance,
                        ", ".join(scored.matched_keywords),
                        paper.title,
                    )
                results.append(scored)
                if self.settings.run_once and scored.score < self.settings.min_relevance_score:
                    logger.debug(
                        "[BelowThreshold] %s below MIN_RELEVANCE_SCORE %.1f (can still be selected by MIN_DAILY_PUSH_COUNT)",
                        paper.arxiv_id,
                        self.settings.min_relevance_score,
                    )
            except Exception as exc:
                logger.warning("Failed to score paper %s: %s", paper.arxiv_id, exc)
            if interval > 0 and index < len(papers) - 1:
                time.sleep(interval)
        return results

    def _select_top(self, scored: list[ScoredPaper]) -> list[ScoredPaper]:
        scored.sort(key=lambda item: item.score, reverse=True)
        threshold_selected = [item for item in scored if item.score >= self.settings.min_relevance_score]
        min_push_count = max(self.settings.min_daily_push_count, 0)

        if len(threshold_selected) > min_push_count:
            logger.info(
                "Selected by threshold only: %d papers (MIN_RELEVANCE_SCORE=%.1f, MIN_DAILY_PUSH_COUNT=%d)",
                len(threshold_selected),
                self.settings.min_relevance_score,
                min_push_count,
            )
            return threshold_selected

        selected_count = min(min_push_count, len(scored))
        logger.info(
            "Threshold-selected papers (%d) are not greater than MIN_DAILY_PUSH_COUNT=%d, backfilling to %d papers",
            len(threshold_selected),
            min_push_count,
            selected_count,
        )
        return scored[:selected_count]
