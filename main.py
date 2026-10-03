from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio
import logging
from extractors import extract_metadata
from typing import Optional
from fastapi import UploadFile, File
from extractor_api import process_file_extraction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("komify_scraper")

import os
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:4001")
BACKEND_LOGS_URL = f"{BACKEND_URL}/system-logs"

# Proxy configuration (optional)
# Set SCRAPER_PROXY for a global proxy, e.g. "http://user:pass@host:port"
# Or per-domain overrides: SCRAPER_PROXY_NHENTAI, SCRAPER_PROXY_EHENTAI
SCRAPER_PROXY = os.getenv("SCRAPER_PROXY", "")
SCRAPER_PROXY_NHENTAI = os.getenv("SCRAPER_PROXY_NHENTAI", SCRAPER_PROXY)
SCRAPER_PROXY_EHENTAI = os.getenv("SCRAPER_PROXY_EHENTAI", SCRAPER_PROXY)


def get_proxy_for_url(url: str) -> dict:
    """Return curl_cffi proxies dict based on URL domain."""
    proxy = ""
    if "nhentai" in url:
        proxy = SCRAPER_PROXY_NHENTAI
    elif "e-hentai" in url or "exhentai" in url:
        proxy = SCRAPER_PROXY_EHENTAI
    else:
        proxy = SCRAPER_PROXY

    if proxy:
        return {"http": proxy, "https": proxy}
    return {}


async def log_to_backend(
    level: str, message: str, stack_trace: str = None, context: dict = None
):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                BACKEND_LOGS_URL,
                json={
                    "level": level,
                    "source": "SCRAPER",
                    "message": message,
                    "stack_trace": stack_trace,
                    "context": context,
                },
            )
    except Exception as e:
        logger.error(f"Failed to send log to backend: {e}")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Komify Scraper Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeRequest(BaseModel):
    url: str


@app.post("/api/v1/scrape")
async def trigger_scrape(request: ScrapeRequest):
    logger.info(f"Scraping: {request.url}")
    if not request.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        from curl_cffi import requests as c_requests

        cookies = {}
        if "e-hentai.org" in request.url:
            cookies["nw"] = "1"

        def fetch_page():
            if (
                "hitomi.la" in request.url
                or "doujindesu" in request.url
                or "doujin.desu" in request.url
            ):
                try:
                    import sys
                    import asyncio

                    if sys.platform == "win32":
                        asyncio.set_event_loop_policy(
                            asyncio.WindowsProactorEventLoopPolicy()
                        )

                    from playwright.sync_api import sync_playwright

                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        page.goto(request.url)
                        page.wait_for_load_state("networkidle", timeout=15000)
                        html = page.content()
                        browser.close()

                    class MockResponse:
                        status_code = 200
                        text = html

                    return MockResponse()
                except Exception as e:
                    import traceback

                    print(f"PLAYWRIGHT ERROR: {traceback.format_exc()}")
                    raise HTTPException(
                        status_code=500, detail=f"Playwright failed: {repr(e)}"
                    )

            return c_requests.get(
                request.url,
                cookies=cookies,
                timeout=30.0,
                impersonate="chrome",
                proxies=get_proxy_for_url(request.url),
            )

        response = await asyncio.to_thread(fetch_page)

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch page. Status: {response.status_code}",
            )

        metadata = extract_metadata(request.url, response.text)

        return {"success": True, "data": metadata}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")
        import traceback

        asyncio.create_task(
            log_to_backend(
                "ERROR",
                str(e),
                traceback.format_exc(),
                {
                    "url": request.url,
                },
            )
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/extract")
async def extract_file(file: UploadFile = File(...)):
    logger.info(f"Extracting file: {file.filename}")
    return await process_file_extraction(file)
