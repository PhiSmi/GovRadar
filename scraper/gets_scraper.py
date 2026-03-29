"""Scrape NZ Government Electronic Tenders Service (GETS) for IT/digital/health tenders."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

logger = logging.getLogger(__name__)

BASE_URL = "https://www.gets.govt.nz"
INDEX_URL = f"{BASE_URL}/ExternalIndex.htm"

HEADERS = {
    "User-Agent": "GovRadar/1.0 (NZ tender monitor; contact: github.com/govradar)",
}

DELAY = 2.5
MAX_ATTACHMENT_PDFS = 2
MAX_ATTACHMENT_CHARS = 8000

TARGET_KEYWORDS = [
    "information technology",
    "digital",
    "software",
    "data",
    "cloud",
    "cyber",
    "integration",
    "system",
    "platform",
    "health",
    "ict",
    "api",
    "infrastructure",
    "analytics",
    "migration",
    "modernisation",
    "modernization",
    "transformation",
    "professional services",
    "consulting",
    "advisory",
]


@dataclass
class RawTender:
    title: str
    agency: str
    closing_date: str | None
    gets_url: str
    tender_type: str | None = None
    rfx_id: str | None = None
    category: str | None = None
    description: str | None = None
    estimated_value: str | None = None
    status: str = "open"
    attachment_urls: list[str] = field(default_factory=list)
    attachment_text_excerpt: str | None = None
    date_scraped: str | None = None


def _sleep() -> None:
    time.sleep(DELAY)


def _get(url: str, session: requests.Session, params: dict | None = None) -> BeautifulSoup:
    _sleep()
    response = session.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _download(url: str, session: requests.Session) -> requests.Response:
    _sleep()
    response = session.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response


def _parse_listing_rows(soup: BeautifulSoup) -> list[dict]:
    tenders: list[dict] = []
    table = soup.find("table", class_="contentTable")
    if not table:
        for candidate in soup.find_all("table"):
            if candidate.find("a", href=re.compile(r"ExternalTenderDetails")):
                table = candidate
                break
    if not table:
        logger.warning("No tender listing table found")
        return tenders

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = row.find("a", href=re.compile(r"ExternalTenderDetails"))
        if not link:
            continue

        href = link.get("href", "")
        full_url = urljoin(BASE_URL, href) if not href.startswith("http") else href
        texts = [cell.get_text(strip=True) for cell in cells]

        title = link.get_text(strip=True)
        tender_type = None
        closing_date = None
        agency = None
        rfx_id = None

        for index, text in enumerate(texts):
            if re.match(r"^\d{6,}$", text):
                rfx_id = text
            elif text in ("RFP", "RFQ", "RFT", "ROI", "RFI", "ITR", "NOI", "EOI", "RFR"):
                tender_type = text
            elif re.search(r"\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", text, re.I):
                closing_date = text
            elif index == len(texts) - 1 and len(text) > 3:
                agency = text

        tenders.append(
            {
                "title": title,
                "agency": agency,
                "closing_date": closing_date,
                "gets_url": full_url,
                "tender_type": tender_type,
                "rfx_id": rfx_id,
            }
        )

    return tenders


def _extract_attachment_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        text = anchor.get_text(" ", strip=True).lower()
        full_url = urljoin(BASE_URL, href)

        if full_url in seen:
            continue

        hint = " ".join([href.lower(), text])
        if any(token in hint for token in [".pdf", "download", "document", "specification", "tender document"]):
            seen.add(full_url)
            links.append(full_url)

    return links


def _parse_detail_page(soup: BeautifulSoup) -> dict:
    info: dict = {"attachment_urls": _extract_attachment_links(soup)}

    # Try structured overview section first
    overview_section = soup.find("div", class_="tenderOverview") or soup.find("div", id=re.compile(r"overview", re.I))
    if overview_section:
        info["description"] = overview_section.get_text(separator="\n", strip=True)
    else:
        # Look for h2 "Overview" and grab sibling/following content
        overview_heading = soup.find(["h2", "h3"], string=re.compile(r"overview", re.I))
        if overview_heading:
            parts: list[str] = []
            for sibling in overview_heading.find_next_siblings():
                tag = sibling.name or ""
                if tag in ("h1", "h2", "h3") and sibling != overview_heading:
                    break
                text = sibling.get_text(" ", strip=True)
                if text:
                    parts.append(text)
            if parts:
                info["description"] = "\n".join(parts)[:5000]

        # Final fallback: largest div that does NOT contain the nav menu
        if "description" not in info:
            nav_terms = {"create account", "current tenders", "late tenders", "closed tenders"}
            longest = ""
            for div in soup.find_all("div"):
                text = div.get_text(" ", strip=True)
                lower = text.lower()
                if any(term in lower for term in nav_terms):
                    continue
                if len(text) > len(longest):
                    longest = text
            if len(longest) > 200:
                info["description"] = longest[:5000]

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) != 2:
            continue
        label = cells[0].get_text(" ", strip=True).lower()
        value = cells[1].get_text(" ", strip=True)
        if "categor" in label:
            info["category"] = value
        elif "tender type" in label or "rfx type" in label:
            info["tender_type"] = value
        elif "value" in label and ("estimate" in label or "contract" in label):
            info["estimated_value"] = value
        elif "close" in label and "date" in label:
            info["closing_date"] = value
        elif "organisation" in label or "agency" in label or "department" in label:
            info["agency"] = value
        elif "status" in label:
            info["status_label"] = value

    return info


def _extract_pdf_text(url: str, session: requests.Session) -> str:
    try:
        response = _download(url, session)
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            return ""

        reader = PdfReader(BytesIO(response.content))
        chunks: list[str] = []
        for page in reader.pages[:6]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
        return text[:MAX_ATTACHMENT_CHARS]
    except Exception as error:
        logger.debug("Could not extract PDF text from %s: %s", url, error)
        return ""


def _extract_attachment_text(urls: list[str], session: requests.Session) -> str:
    excerpts: list[str] = []
    for url in urls[:MAX_ATTACHMENT_PDFS]:
        text = _extract_pdf_text(url, session)
        if text:
            excerpts.append(text)
        if sum(len(item) for item in excerpts) >= MAX_ATTACHMENT_CHARS:
            break
    return "\n\n".join(excerpts)[:MAX_ATTACHMENT_CHARS]


def _is_relevant(title: str, description: str | None = None) -> bool:
    combined = (title + " " + (description or "")).lower()
    return any(keyword in combined for keyword in TARGET_KEYWORDS)


def _parse_closing_date(date_str: str | None) -> str | None:
    if not date_str:
        return None

    cleaned = re.sub(r"\(.*?\)", "", date_str).strip()
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", cleaned)

    for fmt in (
        "%d %b %Y %I:%M %p",
        "%d %B %Y %I:%M %p",
        "%d %b %Y %H:%M",
        "%d %B %Y %H:%M",
        "%d %b %Y",
        "%d %B %Y",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.debug("Could not parse date: %s", date_str)
    return None


def _determine_status(closing_iso: str | None, status_label: str | None) -> str:
    # Only check the structured status label from the metadata table — never
    # the full description, which includes GETS nav-menu text like "Closed tenders"
    # that would false-positive every single tender.
    if status_label:
        label = status_label.strip().lower()
        if any(term in label for term in ["awarded", "cancelled", "canceled", "closed"]):
            return "closed"

    if closing_iso:
        try:
            if datetime.strptime(closing_iso, "%Y-%m-%d").date() < datetime.now(timezone.utc).date():
                return "closed"
        except ValueError:
            pass

    return "open"


def scrape_gets(max_pages: int = 11) -> list[RawTender]:
    session = requests.Session()
    all_listings: list[dict] = []

    logger.info("Starting GETS scrape...")
    for page in range(1, max_pages + 1):
        logger.info("Fetching listing page %s...", page)
        try:
            soup = _get(INDEX_URL, session, params=None if page == 1 else {"page": page})
            rows = _parse_listing_rows(soup)
            if not rows:
                logger.info("No results on page %s, stopping pagination", page)
                break
            all_listings.extend(rows)
            logger.info("  Found %s tenders on page %s", len(rows), page)
        except Exception as error:
            logger.error("Error fetching page %s: %s", page, error)
            break

    logger.info("Total listings found: %s", len(all_listings))

    results: list[RawTender] = []
    scrape_stamp = datetime.now(timezone.utc).isoformat()

    for listing in all_listings:
        title = listing.get("title", "")
        detail_url = listing["gets_url"]
        detail_info: dict = {}

        try:
            logger.info("  Fetching detail: %s...", title[:60])
            detail_soup = _get(detail_url, session)
            detail_info = _parse_detail_page(detail_soup)
        except Exception as error:
            logger.warning("  Could not fetch detail page %s: %s", detail_url, error)

        attachment_urls = detail_info.get("attachment_urls", [])
        attachment_text = _extract_attachment_text(attachment_urls, session) if attachment_urls else ""
        description = detail_info.get("description")
        relevance_text = "\n\n".join(part for part in [description, attachment_text] if part)

        if not _is_relevant(title, relevance_text):
            continue

        closing_raw = detail_info.get("closing_date") or listing.get("closing_date")
        closing_iso = _parse_closing_date(closing_raw)
        status = _determine_status(closing_iso, detail_info.get("status_label"))

        tender = RawTender(
            title=title,
            agency=detail_info.get("agency") or listing.get("agency") or "",
            closing_date=closing_iso,
            gets_url=detail_url,
            tender_type=detail_info.get("tender_type") or listing.get("tender_type"),
            rfx_id=listing.get("rfx_id"),
            category=detail_info.get("category"),
            description=relevance_text or None,
            estimated_value=detail_info.get("estimated_value"),
            status=status,
            attachment_urls=attachment_urls,
            attachment_text_excerpt=attachment_text or None,
            date_scraped=scrape_stamp,
        )
        results.append(tender)
        logger.info("  Relevant: %s", title[:60])

    logger.info("Relevant tenders: %s / %s", len(results), len(all_listings))
    return results
