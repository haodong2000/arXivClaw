from __future__ import annotations

from datetime import datetime
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from arxivclaw.clients.arxiv_client import ArxivClient
from arxivclaw.clients.email_client import EmailClient
from arxivclaw.clients.llm_client import LLMClient
from arxivclaw.config import settings
from arxivclaw.pipeline import RecommenderPipeline
from arxivclaw.storage.state_store import StateStore


def build_pipeline() -> RecommenderPipeline:
    arxiv_client = ArxivClient()
    llm_client = LLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    email_client = EmailClient(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        email_from=settings.email_from,
        email_to=settings.email_to,
    )
    state_store = StateStore(db_path=settings.state_db_path)

    return RecommenderPipeline(
        settings=settings,
        arxiv_client=arxiv_client,
        llm_client=llm_client,
        email_client=email_client,
        state_store=state_store,
    )


def run_job() -> None:
    logging.info("Starting scheduled job at %s", datetime.now().isoformat())
    pipeline = build_pipeline()
    result = pipeline.run_once()
    logging.info("Job finished: %s", result)


def send_startup_email_notice() -> None:
    if not settings.init_email_on_startup:
        return

    email_client = EmailClient(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        email_from=settings.email_from,
        email_to=settings.email_to,
    )

    summary_items = [
        ("ARXIV_QUERY", "arXiv query categories/keywords used to fetch papers", f"{settings.arxiv_query}"),
        ("ARXIV_MAX_RESULTS", "max fetched papers per run", f"{settings.arxiv_max_results}"),
        ("KEYWORDS", "matching keywords", f"{', '.join(settings.keyword_list) if settings.keyword_list else '(empty)'}"),
        ("MIN_RELEVANCE_SCORE", "primary score threshold", f"{settings.min_relevance_score}"),
        ("MIN_DAILY_PUSH_COUNT", "minimum papers to send via backfill", f"{settings.min_daily_push_count}"),
        ("LLM_MODEL", "LLM model", f"{settings.llm_model}"),
        ("LLM_REQUEST_INTERVAL_SECONDS", "sleep between scoring requests", f"{settings.llm_request_interval_seconds}s"),
        ("TIMEZONE", "scheduler timezone", f"{settings.timezone}"),
        ("RUN_TIME", "weekday schedule", f"{settings.run_hour:02d}:{settings.run_minute:02d}"),
        ("RUN_ONCE", "run-once debug mode", f"{settings.run_once}"),
        ("STATE_DB_PATH", "state db path", f"{settings.state_db_path}"),
    ]

    try:
        email_client.send_init_notice(summary_items)
        logging.info("Startup init email sent")
    except Exception as exc:
        logging.warning("Failed to send startup init email: %s", exc)


def main() -> None:
    level = logging.DEBUG if settings.run_once else getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if settings.run_once:
        logging.info("RUN_ONCE mode: verbose logging enabled and state.db ignored")

    send_startup_email_notice()

    if settings.run_once:
        run_job()
        return

    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=settings.run_hour,
        minute=settings.run_minute,
        timezone=settings.timezone,
    )
    scheduler.add_job(run_job, trigger=trigger, id="daily_arxiv_digest", replace_existing=True)
    logging.info(
        "Scheduler started. Job runs at %02d:%02d (%s), weekdays only.",
        settings.run_hour,
        settings.run_minute,
        settings.timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
