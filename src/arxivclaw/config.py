from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    arxiv_query: str = Field(default="cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV", alias="ARXIV_QUERY")
    arxiv_max_results: int = Field(default=500, alias="ARXIV_MAX_RESULTS")
    arxiv_timeout_seconds: int = Field(default=30, alias="ARXIV_TIMEOUT_SECONDS")
    arxiv_max_retries: int = Field(default=3, alias="ARXIV_MAX_RETRIES")
    arxiv_retry_backoff_seconds: float = Field(default=2.0, alias="ARXIV_RETRY_BACKOFF_SECONDS")

    llm_base_url: str = Field(alias="LLM_BASE_URL")
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_model: str = Field(default="gemini-3.1-flash-lite-preview", alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_request_interval_seconds: float = Field(default=5.0, alias="LLM_REQUEST_INTERVAL_SECONDS")

    keywords: str = Field(default="", alias="KEYWORDS")
    min_relevance_score: float = Field(default=50, alias="MIN_RELEVANCE_SCORE")
    min_daily_push_count: int = Field(default=50, alias="MIN_DAILY_PUSH_COUNT")

    smtp_host: str = Field(alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(alias="SMTP_USER")
    smtp_password: str = Field(alias="SMTP_PASSWORD")
    email_from: str = Field(alias="EMAIL_FROM")
    email_to: str = Field(alias="EMAIL_TO")

    state_db_path: str = Field(default="data/state.db", alias="STATE_DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="America/Los_Angeles", alias="TIMEZONE")
    run_hour: int = Field(default=14, alias="RUN_HOUR")
    run_minute: int = Field(default=0, alias="RUN_MINUTE")
    run_once: bool = Field(default=False, alias="RUN_ONCE")
    init_email_on_startup: bool = Field(default=True, alias="INIT_EMAIL_ON_STARTUP")

    @property
    def keyword_list(self) -> list[str]:
        return [word.strip() for word in self.keywords.split(",") if word.strip()]


settings = Settings()
