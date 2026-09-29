import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class NhentaiExtractor:
    def extract(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        result = {
            "title": "",
            "alternative_title": "",
            "parodies": [],
            "characters": [],
            "tags": [],
            "artists": [],
            "groups": [],
        }

        h1 = soup.select_one("h1.title")
        if h1:
            before = h1.select_one(".before")
            pretty = h1.select_one(".pretty")
            after = h1.select_one(".after")

            before_text = before.get_text(strip=True) if before else ""
            pretty_text = pretty.get_text(strip=True) if pretty else ""
            after_text = after.get_text(strip=True) if after else ""

            parody_match = re.search(r"\([^)]+\)", after_text)
            parody = parody_match.group(0) if parody_match else ""

            parts = [p for p in [before_text, pretty_text, parody] if p]
            result["title"] = " ".join(parts).strip()

        h2 = soup.select_one("h2.title")
        if h2:
            result["alternative_title"] = h2.get_text(strip=True)

        for container in soup.select(".tag-container"):
            label_text = (
                container.contents[0].strip().replace(":", "").lower()
                if container.contents
                else ""
            )

            values = [tag.get_text(strip=True) for tag in container.select(".name")]

            if "parodies" in label_text:
                result["parodies"] = values
            elif "characters" in label_text:
                result["characters"] = values
            elif "tags" in label_text:
                result["tags"] = values
            elif "artists" in label_text:
                result["artists"] = values
            elif "groups" in label_text:
                result["groups"] = values

        return result


def extract_metadata(url: str, html: str, scraper_code: str = None) -> dict:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if scraper_code == "NHENTAI" or "nhentai.net" in domain or "nhentai.com" in domain or "nhentai.xxx" in domain:
        return NhentaiExtractor().extract(html)

    return NhentaiExtractor().extract(html)
