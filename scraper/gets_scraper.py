"""Scrape NZ Government Electronic Tenders Service (GETS) for IT/digital/health tenders."""

from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.gets.govt.nz"
INDEX_URL = f"{BASE_URL}/ExternalIndex.htm"
SEARCH_URL = f"{BASE_URL}/ExternalSearchResults.htm"

HEADERS = {
    "User-Agent": "GovRadar/1.0 (NZ tender monitor; contact: github.com/govradar)",
}

DELAY = 2.5  # seconds between requests — be respectful

# Target UNSPSC categories (IT, digital, health, professional services)
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
    "ICT",
    "API",
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


def _get(url: str, session: requests.Session, params: dict | None = None) -> BeautifulSoup:
    time.sleep(DELAY)
    resp = session.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_listing_rows(soup: BeautifulSoup) -> list[dict]:
    """Parse the tender listing table on the search/index page."""
    tenders = []
    table = soup.find("table", class_="contentTable")
    if not table:
        # Try any table with tender-like content
        tables = soup.find_all("table")
        for t in tables:
            if t.find("a", href=re.compile(r"ExternalTenderDetails")):
                table = t
                break
    if not table:
        logger.warning("No tender listing table found")
        return tenders

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = row.find("a", href=re.compile(r"ExternalTenderDetails"))
        if not link:
            continue

        href = link.get("href", "")
        full_url = urljoin(BASE_URL, href) if not href.startswith("http") else href

        # Extract text from cells — layout varies but typically:
        # RFx ID | Reference | Title | Tender Type | Close Date | Organisation
        texts = [c.get_text(strip=True) for c in cells]

        title = link.get_text(strip=True)
        tender_type = None
        closing_date = None
        agency = None
        rfx_id = None

        # Try to identify columns by content patterns
        for i, text in enumerate(texts):
            if re.match(r"^\d{6,}$", text):
                rfx_id = text
            elif text in ("RFP", "RFQ", "RFT", "ROI", "RFI", "ITR", "NOI", "EOI", "RFR"):
                tender_type = text
            elif re.search(r"\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", text, re.I):
                closing_date = text
            elif i == len(texts) - 1 and len(text) > 3:
                agency = text

        tenders.append({
            "title": title,
            "agency": agency,
            "closing_date": closing_date,
            "gets_url": full_url,
            "tender_type": tender_type,
            "rfx_id": rfx_id,
        })

    return tenders


def _parse_detail_page(soup: BeautifulSoup) -> dict:
    """Extract detail fields from a tender detail page."""
    info: dict = {}

    # Get overview/description
    overview_section = soup.find("div", class_="tenderOverview") or soup.find(
        "div", id=re.compile(r"overview", re.I)
    )
    if overview_section:
        info["description"] = overview_section.get_text(separator="\n", strip=True)
    else:
        # Fallback: look for the largest text block after the metadata
        for div in soup.find_all("div"):
            text = div.get_text(strip=True)
            if len(text) > 200 and "overview" not in info:
                info["description"] = text[:5000]

    # Parse key-value metadata rows
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
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

    return info


def _is_relevant(title: str, description: str | None = None) -> bool:
    """Quick relevance check — does the tender look IT/digital/health related?"""
    combined = (title + " " + (description or "")).lower()
    return any(kw.lower() in combined for kw in TARGET_KEYWORDS)


def _parse_closing_date(date_str: str | None) -> str | None:
    """Try to parse GETS date formats into ISO date string."""
    if not date_str:
        return None
    # Remove timezone info like "(NZST)" or "(NZDT)"
    cleaned = re.sub(r"\(.*?\)", "", date_str).strip()
    for fmt in (
        "%d %b %Y %I:%M %p",
        "%d %b %Y %H:%M",
        "%d %b %Y",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.debug(f"Could not parse date: {date_str}")
    return None


def scrape_gets(max_pages: int = 11) -> list[RawTender]:
    """Scrape GETS listing pages and detail pages for relevant tenders.

    Args:
        max_pages: Maximum listing pages to crawl (25 tenders per page).

    Returns:
        List of RawTender objects with descriptions populated from detail pages.
    """
    session = requests.Session()
    all_listings: list[dict] = []

    # Scrape listing pages
    logger.info("Starting GETS scrape...")
    for page in range(1, max_pages + 1):
        logger.info(f"Fetching listing page {page}...")
        try:
            if page == 1:
                soup = _get(INDEX_URL, session)
            else:
                soup = _get(INDEX_URL, session, params={"page": page})

            rows = _parse_listing_rows(soup)
            if not rows:
                logger.info(f"No results on page {page}, stopping pagination")
                break

            all_listings.extend(rows)
            logger.info(f"  Found {len(rows)} tenders on page {page}")
        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            break

    logger.info(f"Total listings found: {len(all_listings)}")

    # Filter for relevant tenders by title first
    results: list[RawTender] = []
    for listing in all_listings:
        title = listing.get("title", "")

        # Fetch detail page for every tender to check full description
        detail_url = listing["gets_url"]
        detail_info = {}
        try:
            logger.info(f"  Fetching detail: {title[:60]}...")
            detail_soup = _get(detail_url, session)
            detail_info = _parse_detail_page(detail_soup)
        except Exception as e:
            logger.warning(f"  Could not fetch detail page {detail_url}: {e}")

        description = detail_info.get("description")

        if not _is_relevant(title, description):
            continue

        closing_raw = detail_info.get("closing_date") or listing.get("closing_date")
        closing_iso = _parse_closing_date(closing_raw)

        # Determine status from closing date
        status = "open"
        if closing_iso:
            try:
                if datetime.strptime(closing_iso, "%Y-%m-%d").date() < datetime.utcnow().date():
                    status = "closed"
            except ValueError:
                pass

        tender = RawTender(
            title=title,
            agency=detail_info.get("agency") or listing.get("agency") or "",
            closing_date=closing_iso,
            gets_url=detail_url,
            tender_type=detail_info.get("tender_type") or listing.get("tender_type"),
            rfx_id=listing.get("rfx_id"),
            category=detail_info.get("category"),
            description=description,
            estimated_value=detail_info.get("estimated_value"),
            status=status,
        )
        results.append(tender)
        logger.info(f"  ✓ Relevant: {title[:60]}")

    logger.info(f"Relevant tenders: {len(results)} / {len(all_listings)}")
    return results
