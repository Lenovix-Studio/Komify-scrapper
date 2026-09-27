from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import logging
from extractors import extract_metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("komify_scraper")

app = FastAPI(title="Komify Scraper Service")


class ScrapeRequest(BaseModel):
    url: str


@app.post("/api/v1/scrape")
async def trigger_scrape(request: ScrapeRequest):
    logger.info(f"Scraping: {request.url}")
    if not request.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        cookies = {}
        if "e-hentai.org" in request.url:
            cookies["nw"] = "1"

        async with httpx.AsyncClient(timeout=30.0, cookies=cookies) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            }
            response = await client.get(request.url, headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch page. Status: {response.status_code}",
                )

            metadata = extract_metadata(request.url, response.text)

            return {"success": True, "data": metadata}

    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
