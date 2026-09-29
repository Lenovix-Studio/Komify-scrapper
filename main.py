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

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:4001")
BACKEND_LOGS_URL = f"{BACKEND_URL}/system-logs"


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
    scraper_code: Optional[str] = None


@app.post("/api/v1/scrape")
async def trigger_scrape(request: ScrapeRequest):
    logger.info(f"Scraping: {request.url}")
    if not request.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        cookies = {}
        if "e-hentai.org" in request.url or "nhentai" in request.url:
            cookies["nw"] = "1"

        from urllib.parse import urlparse

        parsed_url = urlparse(request.url)
        referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        async with httpx.AsyncClient(
            timeout=30.0, cookies=cookies, follow_redirects=True
        ) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Referer": referer,
            }
            response = await client.get(request.url, headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch page. Status: {response.status_code}",
                )

            metadata = extract_metadata(
                request.url, response.text, request.scraper_code
            )

            return {"success": True, "data": metadata}

    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")
        import traceback

        asyncio.create_task(
            log_to_backend(
                "ERROR",
                str(e),
                traceback.format_exc(),
                {"url": request.url, "scraper_code": request.scraper_code},
            )
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/extract")
async def extract_file(file: UploadFile = File(...)):
    logger.info(f"Extracting file: {file.filename}")
    return await process_file_extraction(file)
