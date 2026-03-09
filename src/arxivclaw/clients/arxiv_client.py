from __future__ import annotations

from datetime import datetime
import html
import logging
import time
import xml.etree.ElementTree as ET

import httpx

from arxivclaw.models import Paper

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
logger = logging.getLogger(__name__)


class ArxivClient:
    def __init__(
        self,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def fetch_papers(self, query: str, max_results: int) -> list[Paper]:
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max_results,
        }
        timeout = httpx.Timeout(timeout=self._timeout_seconds, connect=min(self._timeout_seconds, 10.0))
        headers = {
            "User-Agent": "arXivClaw/1.0 (+https://github.com/haodong2000/arXivClaw)",
        }
        with httpx.Client(timeout=timeout, headers=headers) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    resp = client.get(ARXIV_API_URL, params=params)
                    resp.raise_for_status()
                    return self._parse_feed(resp.text)
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    retryable = status_code == 429 or status_code >= 500
                    if not retryable or attempt >= self._max_retries:
                        raise
                    wait_seconds = self._retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "arXiv request failed with status %s (attempt %d/%d), retrying in %.1fs",
                        status_code,
                        attempt + 1,
                        self._max_retries + 1,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self._max_retries:
                        raise
                    wait_seconds = self._retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "arXiv request error: %s (attempt %d/%d), retrying in %.1fs",
                        exc,
                        attempt + 1,
                        self._max_retries + 1,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)

        return []

    def _parse_feed(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        entries = root.findall("atom:entry", ATOM_NS)
        papers: list[Paper] = []
        for entry in entries:
            arxiv_id = self._find_text(entry, "atom:id").split("/")[-1]
            title = html.unescape(self._find_text(entry, "atom:title").strip().replace("\n", " "))
            summary = html.unescape(self._find_text(entry, "atom:summary").strip().replace("\n", " "))
            published_str = self._find_text(entry, "atom:published")
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            authors = [
                a.find("atom:name", ATOM_NS).text.strip()
                for a in entry.findall("atom:author", ATOM_NS)
                if a.find("atom:name", ATOM_NS) is not None and a.find("atom:name", ATOM_NS).text
            ]
            categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
            links = [lnk.attrib.get("href", "") for lnk in entry.findall("atom:link", ATOM_NS)]
            link = next((i for i in links if i.startswith("https://arxiv.org/abs/")), self._find_text(entry, "atom:id"))

            papers.append(
                Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    summary=summary,
                    published_at=published_at,
                    link=link,
                    categories=categories,
                )
            )
        return papers

    @staticmethod
    def _find_text(node: ET.Element, xpath: str) -> str:
        found = node.find(xpath, ATOM_NS)
        if found is None or found.text is None:
            return ""
        return found.text
