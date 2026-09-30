import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class NhentaiExtractor:
    """Handles nhentai.net, nhentai.to, nhentai.com, nhentai.xxx, imhentai.to (similar structure)"""

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

        h1_class = soup.select_one("h1.title")
        if h1_class:
            before = h1_class.select_one(".before")
            pretty = h1_class.select_one(".pretty")
            after = h1_class.select_one(".after")
            before_text = before.get_text(strip=True) if before else ""
            pretty_text = pretty.get_text(strip=True) if pretty else ""
            after_text = after.get_text(strip=True) if after else ""
            parody_match = re.search(r"\([^)]+\)", after_text)
            parody = parody_match.group(0) if parody_match else ""
            parts = [p for p in [before_text, pretty_text, parody] if p]
            result["title"] = " ".join(parts).strip()
        else:
            h1 = soup.select_one("#info h1") or soup.select_one("h1")
            if h1:
                result["title"] = h1.get_text(strip=True)

        h2_class = soup.select_one("h2.title")
        if h2_class:
            result["alternative_title"] = h2_class.get_text(strip=True)
        else:
            h2 = soup.select_one("#info h2") or soup.select_one("h2")
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


class Hentai2ReadExtractor:
    """Handles hentai2read.com"""

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

        breadcrumbs = soup.select('.breadcrumb li span[itemprop="name"]')
        if breadcrumbs:
            result["title"] = breadcrumbs[-1].get_text(strip=True)
        else:
            h3 = soup.select_one("h3.block-title")
            if h3:
                result["title"] = h3.get_text(strip=True).replace(" Chapters", "")

        for li in soup.select("ul.list-simple-mini li, .info-list li"):
            b_tag = li.select_one("b")
            if not b_tag:
                continue

            label = b_tag.get_text(strip=True).lower()

            values = []
            for a in b_tag.find_next_siblings("a"):
                val = a.get_text(strip=True)
                if val and val != "-":
                    values.append(val)

            if not values:
                for p in b_tag.find_next_siblings("p"):
                    val = p.get_text(strip=True)
                    if val and val != "-":
                        values.extend(
                            [v.strip() for v in val.split(",") if v.strip() != "-"]
                        )

            if "author" in label or "artist" in label:
                result["artists"].extend(values)
                result["artists"] = list(dict.fromkeys(result["artists"]))
            elif "group" in label or "circle" in label:
                result["groups"].extend(values)
                result["groups"] = list(dict.fromkeys(result["groups"]))
            elif "parody" in label or "series" in label:
                result["parodies"].extend(values)
                result["parodies"] = list(dict.fromkeys(result["parodies"]))
            elif "content" in label or "tag" in label or "category" in label:
                result["tags"].extend(values)
                result["tags"] = list(dict.fromkeys(result["tags"]))
            elif "character" in label:
                result["characters"].extend(values)
                result["characters"] = list(dict.fromkeys(result["characters"]))

        if not result["groups"] and result["artists"]:
            result["groups"] = list(result["artists"])

        return result


class ImhentaiExtractor:
    """Handles imhentai.xxx"""

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

        h1 = soup.select_one("h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        h2 = soup.select_one("p.subtitle, h2")
        if h2:
            result["alternative_title"] = h2.get_text(strip=True)

        for row in soup.select(".galleries_info"):
            label_span = row.select_one(".tags_text")
            if not label_span:
                continue
            label = label_span.get_text(strip=True).lower().rstrip(":")

            vals = []
            for a in row.select("a.tag"):
                span = a.select_one(".split_tag")
                if span:
                    span.decompose()
                badge = a.select_one(".badge")
                if badge:
                    badge.decompose()
                val = a.get_text(strip=True)
                if val:
                    vals.append(val)

            if "parod" in label or "series" in label:
                result["parodies"] = vals
            elif "character" in label:
                result["characters"] = vals
            elif "tag" in label:
                result["tags"] = vals
            elif "artist" in label:
                result["artists"] = vals
            elif "group" in label:
                result["groups"] = (
                    [v for v in vals if v.lower() != "group"] if len(vals) > 1 else vals
                )

        return result


class DoujindesuExtractor:
    """Handles doujindesu.tv and doujin.desu.xxx SPA"""

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

        h1 = soup.select_one("h1.entry-title, h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        for row in soup.select(
            ".infox .fmed, .infox .fli, .spe span, .info-content span"
        ):
            b_tag = row.select_one("b")
            if not b_tag:
                continue
            label = b_tag.get_text(strip=True).lower().rstrip(":")
            b_tag.decompose()
            values = [a.get_text(strip=True) for a in row.select("a")]
            if not values:
                values = [
                    v.strip() for v in row.get_text(strip=True).split(",") if v.strip()
                ]
            self._map_values(result, label, values)

        if not result["tags"]:
            for el in soup.select("span, h3"):
                t = el.get_text(strip=True).lower()
                if t in [
                    "alternative titles",
                    "series",
                    "characters",
                    "genres",
                    "authors",
                    "groups",
                ]:
                    parent = el.parent
                    if not parent:
                        continue
                    vals = [tag.get_text(strip=True) for tag in parent.select("a, p")]
                    self._map_values(result, t, vals)

        return result

    def _map_values(self, result, label, values):
        if "author" in label or "artist" in label:
            result["artists"] = values
        elif "group" in label or "circle" in label:
            result["groups"] = values
        elif "parody" in label or "series" in label or "parodi" in label:
            result["parodies"] = values
        elif "genre" in label or "tag" in label:
            result["tags"] = values
        elif "character" in label or "karakter" in label:
            result["characters"] = values
        elif (
            "alternative" in label or "judul" in label or "alternative titles" in label
        ):
            result["alternative_title"] = ", ".join(values) if values else ""


class HentaiNameExtractor:
    """Handles hentai.name"""

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

        h1 = soup.select_one("h1.detail-title, h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        for row in soup.select(".detail-info-list li, .info-list li, .info-item"):
            label_tag = row.select_one("label, .info-label, b, strong")
            links = row.select("a")
            if not label_tag:
                continue
            label = label_tag.get_text(strip=True).lower().rstrip(":")
            values = [a.get_text(strip=True) for a in links] if links else []

            if "author" in label or "artist" in label:
                result["artists"].extend(values)
            elif "group" in label or "circle" in label:
                result["groups"].extend(values)
            elif "parody" in label or "series" in label:
                result["parodies"] = values
            elif "tag" in label or "genre" in label:
                result["tags"] = values
            elif "character" in label:
                result["characters"].extend(values)

        return result


class HentaieraExtractor:
    """Handles hentaiera.com"""

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

        h1 = soup.select_one("h1, .gallery-title")
        if h1:
            result["title"] = h1.get_text(strip=True)

        subtitle = soup.select_one("p.subtitle")
        if subtitle:
            result["alternative_title"] = subtitle.get_text(strip=True)

        for li in soup.select("ul.galleries_info li, ul.gallery-meta li, .meta li"):
            label_tag = li.select_one(".tags_text, .label, b, strong")
            if not label_tag:
                continue
            label = label_tag.get_text(strip=True).lower().rstrip(":")

            values = []
            for a in li.select(".info_tags a, a.tag, a"):
                name_span = a.select_one(".item_name")
                if name_span:
                    v = name_span.get_text(strip=True)
                else:
                    v = a.get_text(strip=True)

                if v and v.lower() != label:
                    values.append(v)

            values = list(dict.fromkeys(values))

            if "author" in label or "artist" in label:
                result["artists"] = values
            elif "group" in label or "circle" in label:
                result["groups"] = values
            elif "parod" in label or "series" in label:
                result["parodies"].extend(values)
            elif "tag" in label or "genre" in label or "categor" in label:
                result["tags"].extend(values)
            elif "character" in label:
                result["characters"] = values

        for k in ["artists", "groups", "parodies", "tags", "characters"]:
            result[k] = list(dict.fromkeys(result[k]))
        return result


class HitomiExtractor:
    """Handles hitomi.la"""

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

        title_tag = soup.select_one("title")
        if title_tag:
            t = title_tag.get_text(strip=True)
            t = t.replace(" - Hitomi.la", "").replace(" | Hitomi.la", "")
            result["title"] = t

        h1 = soup.select_one("h1#gallery-brand, .gallery-brand a")
        if h1 and h1.get_text(strip=True):
            result["title"] = h1.get_text(strip=True)

        for h2 in soup.select("h2"):
            a_tags = h2.select("a")
            for a in a_tags:
                result["artists"].append(a.get_text(strip=True))

        for row in soup.select(".gallery-info tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            values = [
                a.get_text(strip=True).replace(" ♀", "").replace(" ♂", "")
                for a in cells[1].select("a")
            ]

            if "group" in label:
                result["groups"] = values
            elif "series" in label or "parody" in label:
                result["parodies"] = values
            elif "tag" in label:
                result["tags"] = values
            elif "character" in label:
                result["characters"] = values

        return result


def extract_metadata(url: str, html: str) -> dict:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "nhentai" in domain:
        return NhentaiExtractor().extract(html)

    if "imhentai" in domain:
        return ImhentaiExtractor().extract(html)

    if "hentai2read" in domain:
        return Hentai2ReadExtractor().extract(html)

    if "doujindesu" in domain or "doujin.desu" in domain:
        return DoujindesuExtractor().extract(html)

    if "hentai.name" in domain:
        return HentaiNameExtractor().extract(html)

    if "hentaiera" in domain:
        return HentaieraExtractor().extract(html)

    if "hitomi" in domain:
        return HitomiExtractor().extract(html)

    return NhentaiExtractor().extract(html)
