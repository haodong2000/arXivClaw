from __future__ import annotations

from datetime import datetime
from email.mime.text import MIMEText
import html
import smtplib

from arxivclaw.models import ScoredPaper


class EmailClient:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        email_from: str,
        email_to: str,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._email_from = email_from
        self._email_to = email_to

    def send_digest(self, papers: list[ScoredPaper]) -> None:
        date_str = datetime.now().strftime("%Y%m%d")
        subject = f"arXivClaw | Daily Research Picks | {date_str} ({len(papers)} papers)"
        body = self._build_body(papers)
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self._email_from
        msg["To"] = self._email_to

        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            server.starttls()
            server.login(self._smtp_user, self._smtp_password)
            server.sendmail(self._email_from, [self._email_to], msg.as_string())

    def send_init_notice(self, summary_items: list[tuple[str, str]]) -> None:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"arXivClaw | Startup Confirmation | {date_str}"
        body = self._build_init_body(summary_items)
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self._email_from
        msg["To"] = self._email_to

        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            server.starttls()
            server.login(self._smtp_user, self._smtp_password)
            server.sendmail(self._email_from, [self._email_to], msg.as_string())

    @staticmethod
    def _build_body(papers: list[ScoredPaper]) -> str:
        lines = ["<html><body>"]
        for i, item in enumerate(papers, start=1):
            authors = ", ".join(html.escape(author) for author in item.paper.authors)
            lines.extend(
                [
                    f"<p><strong>{i}. {html.escape(item.paper.title)}</strong><br>",
                    f"Authors: {authors}<br>",
                    f"Score: <strong>{item.score:.1f}</strong> | Relevance: <strong>{html.escape(item.relevance)}</strong><br>",
                    f"Matched keywords: <strong>{html.escape(', '.join(item.matched_keywords))}</strong><br>",
                    f"Link: <a href=\"{html.escape(item.paper.link)}\">{html.escape(item.paper.link)}</a></p>",
                ]
            )
        lines.append("</body></html>")
        return "\n".join(lines)

    @staticmethod
    def _build_init_body(summary_items: list[tuple[str, str]]) -> str:
        lines = [
            "<html><body>",
            "<p><strong>arXivClaw has started successfully.</strong></p>",
            "<p>Current runtime settings overview:</p>",
            "<ul>",
        ]
        for key, desc in summary_items:
            lines.append(f"<li><strong>{html.escape(key)}</strong>: {html.escape(desc)}</li>")
        lines.extend(
            [
                "</ul>",
                "<p>This is a startup notification email. It does not include API keys or passwords.</p>",
                "</body></html>",
            ]
        )
        return "\n".join(lines)
