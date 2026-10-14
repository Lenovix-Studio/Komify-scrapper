from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import logging
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from extractors import extract_metadata
from extractor_api import process_file_extraction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("komify_scraper")

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:4001")
BACKEND_LOGS_URL = f"{BACKEND_URL}/system-logs"

# Proxy configuration & List with Country annotations
PROXY_LIST = [
    "http://ivjnubqy:6d13r4kefqsp@45.38.107.97:6014",  # United Kingdom (London)
    "http://ivjnubqy:6d13r4kefqsp@64.137.96.74:6641",  # Spain (Madrid)
    "http://ivjnubqy:6d13r4kefqsp@198.23.243.226:6361",  # United States (Los Angeles)
    "http://ivjnubqy:6d13r4kefqsp@38.154.185.97:6370",  # United States (Piscataway)
    "http://ivjnubqy:6d13r4kefqsp@84.247.60.125:6095",  # Poland (Warsaw)
    "http://ivjnubqy:6d13r4kefqsp@191.96.254.138:6185",  # United States (Los Angeles)
    "http://ivjnubqy:6d13r4kefqsp@198.46.161.42:5092",  # United States (Los Angeles)
    "http://ivjnubqy:6d13r4kefqsp@64.137.10.153:5803",  # Germany (Frankfurt)
    "http://ivjnubqy:6d13r4kefqsp@104.164.49.38:7693",  # United States (Santa Clara)
    "http://ivjnubqy:6d13r4kefqsp@23.26.71.145:5628",  # United States (Orem)
]


def get_proxy_dict(proxy_url: str) -> Optional[Dict[str, str]]:
    """Return curl_cffi proxies dict or None."""
    if proxy_url:
        return {"http": proxy_url, "https": proxy_url}
    return None


async def log_to_backend(
    level: str,
    message: str,
    stack_trace: Optional[str] = None,
    context: Optional[dict] = None,
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

            # --- LOGIKA ROTASI PROXY OTOMATIS (FALLBACK) ---
            last_exception = None

            for current_proxy in PROXY_LIST:
                proxy_target = current_proxy.split("@")[-1]
                try:
                    logger.info(f"Mencoba fetch menggunakan proxy: {proxy_target}")
                    response = c_requests.get(
                        request.url,
                        cookies=cookies,
                        timeout=15.0,
                        impersonate="chrome",
                        proxies=get_proxy_dict(current_proxy),  # type: ignore
                    )

                    if response.status_code == 200:
                        logger.info(f"Berhasil terhubung via proxy: {proxy_target}")
                        return response

                    if "nhentai.net" in request.url and response.status_code == 429:
                        for mirror in ["nhentai.xxx", "nhentai.to", "nhentai.com"]:
                            mirror_url = request.url.replace("nhentai.net", mirror)
                            m_response = c_requests.get(
                                mirror_url,
                                cookies=cookies,
                                timeout=15.0,
                                impersonate="chrome",
                                proxies=get_proxy_dict(current_proxy),  # type: ignore
                            )
                            if m_response.status_code == 200:
                                return m_response

                    logger.warning(
                        f"Proxy {proxy_target} merespons dengan status {response.status_code}, mencoba proxy berikutnya..."
                    )
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"Proxy {proxy_target} gagal/timeout: {str(e)}. Beralih ke proxy selanjutnya..."
                    )
                    continue

            raise HTTPException(
                status_code=500,
                detail=f"Semua proxy gagal terhubung. Error terakhir: {str(last_exception)}",
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
