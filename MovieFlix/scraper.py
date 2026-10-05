"""
MovieFlix - Web Crawling & Scraping Module
Educational module demonstrating polite, robots.txt-compliant HTML metadata extraction
using BeautifulSoup4 and Requests. Does not bypass paywalls, CAPTCHAs, or access controls.
"""

import sys
import logging
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "MovieFlixScraper/1.0 (+http://localhost:5000/ - Educational College IR Project)"
SCRAPER_TIMEOUT = (3.0, 10.0)


def is_allowed_by_robots(url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """
    Parses and checks the target domain's robots.txt to ensure respectful crawling.
    Returns True if scraping the path is permitted, False otherwise.
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        # Fetch robots.txt with safe timeout
        response = requests.get(
            robots_url,
            headers={"User-Agent": user_agent},
            timeout=5.0
        )
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
            return rp.can_fetch(user_agent, url)
        elif response.status_code in (401, 403):
            # Explicit denial
            return False
        # 404 or others usually means no robots.txt restrictions
        return True
    except Exception as exc:
        logger.warning("Could not verify robots.txt for %s: %s", url, exc)
        # Default to polite assumption if error occurs
        return True


def crawl_page_metadata(url: str, check_robots: bool = True) -> Dict[str, Any]:
    """
    Crawls a permitted public web page and extracts structured metadata:
    - Page Title
    - Meta Description
    - Canonical URL
    - Main Headings (H1, H2)
    - OpenGraph Tags (og:title, og:description, og:image)
    - Extracted Body Snippets

    Adheres to educational and ethical web scraping standards.
    """
    result: Dict[str, Any] = {
        "url": url,
        "success": False,
        "title": None,
        "meta_description": None,
        "canonical_url": None,
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "headings": [],
        "content_snippet": None,
        "error": None,
    }

    if check_robots and not is_allowed_by_robots(url):
        result["error"] = "Access disallowed by target domain's robots.txt policy."
        logger.info("Blocked by robots.txt: %s", url)
        return result

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=SCRAPER_TIMEOUT)
        if response.status_code != 200:
            result["error"] = f"HTTP Error {response.status_code}: {response.reason}"
            return result

        soup = BeautifulSoup(response.content, "html.parser")

        # 1. Page Title
        if soup.title and soup.title.string:
            result["title"] = soup.title.string.strip()

        # 2. Meta Description
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_desc and meta_desc.get("content"):
            result["meta_description"] = meta_desc["content"].strip()

        # 3. Canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            result["canonical_url"] = urljoin(url, canonical["href"].strip())

        # 4. OpenGraph metadata
        og_t = soup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            result["og_title"] = og_t["content"].strip()

        og_d = soup.find("meta", property="og:description")
        if og_d and og_d.get("content"):
            result["og_description"] = og_d["content"].strip()

        og_i = soup.find("meta", property="og:image")
        if og_i and og_i.get("content"):
            result["og_image"] = urljoin(url, og_i["content"].strip())

        # 5. Extract Top Headings
        headings = []
        for tag in soup.find_all(["h1", "h2"]):
            text = tag.get_text(strip=True)
            if text and len(text) > 3:
                headings.append(text)
        result["headings"] = headings[:6]

        # 6. Content Snippet (first 300 characters of meaningful paragraphs)
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 25]
        if paragraphs:
            combined_p = " ".join(paragraphs[:3])
            result["content_snippet"] = combined_p[:350] + ("..." if len(combined_p) > 350 else "")

        result["success"] = True
        return result

    except requests.exceptions.Timeout:
        result["error"] = "Request timed out while fetching URL."
        return result
    except requests.exceptions.RequestException as exc:
        result["error"] = f"Request failure: {str(exc)}"
        return result
    except Exception as exc:
        result["error"] = f"Parsing error: {str(exc)}"
        return result


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print("=" * 60)
    print(f"MovieFlix Web Scraper Demo")
    print(f"Target URL: {test_url}")
    print("=" * 60)
    data = crawl_page_metadata(test_url)
    for key, value in data.items():
        print(f"[{key}]: {value}")
