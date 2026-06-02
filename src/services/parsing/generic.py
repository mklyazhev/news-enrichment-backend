import asyncio
import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.services.parsing.base import ArticleParser, ParsedArticle
from src.services.parsing.keywords import fallback_keywords_from_text

PARSER_VERSION = "html-cascade-v1"


class GenericArticleParser(ArticleParser):
    def __init__(self, timeout_seconds: float = 10, max_retries: int = 2) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def fetch_and_parse(self, url: str) -> ParsedArticle:
        html = await self.fetch_html(url)
        return self.parse_html(html, base_url=url)

    async def fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": "NewsEnrichmentBot/1.0 (+https://example.com/bot)",
            "Accept": "text/html,application/xhtml+xml",
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.2 * (2**attempt))
        raise RuntimeError(f"failed to fetch article: {last_error}")

    def parse_html(self, html: str, base_url: str) -> ParsedArticle:
        soup = BeautifulSoup(html, "lxml")
        json_ld = self._extract_json_ld(soup)
        meta = self._extract_meta(soup)
        self._remove_noise(soup)

        text = self._extract_text(soup)
        images = self._extract_images(soup, base_url)
        tags = self._unique(
            self._meta_values(meta, "article:tag")
            + self._split_many(self._meta_values(meta, "keywords"))
            + self._jsonld_list(json_ld, "keywords")
        )
        categories = self._unique(
            self._meta_values(meta, "article:section")
            + self._meta_values(meta, "section")
            + self._meta_values(meta, "category")
            + self._jsonld_list(json_ld, "articleSection")
        )
        structured_keywords = self._unique(tags + categories)

        summary = (
            self._meta_first(meta, "description")
            or self._meta_first(meta, "og:description")
            or self._jsonld_value(json_ld, "description")
            or self._summarize(text)
        )
        main_image = (
            self._meta_first(meta, "og:image")
            or self._jsonld_image(json_ld)
            or (images[0] if images else None)
        )

        return ParsedArticle(
            full_text=text,
            main_image_url=main_image,
            image_urls=self._unique(([main_image] if main_image else []) + images),
            categories=categories,
            tags=tags,
            author=self._meta_first(meta, "author") or self._meta_first(meta, "article:author") or self._jsonld_author(json_ld),
            views_count=self._extract_counter(soup, "view"),
            comments_count=self._extract_counter(soup, "comment"),
            keywords=self._unique(structured_keywords + fallback_keywords_from_text(text))[:10],
            summary=summary,
            region=self._meta_first(meta, "geo.placename") or self._meta_first(meta, "region"),
            topic=categories[0] if categories else None,
            has_video=bool(soup.select("video, iframe[src*='youtube'], iframe[src*='rutube'], iframe[src*='vimeo']")),
            parser_version=PARSER_VERSION,
        )

    @staticmethod
    def _remove_noise(soup: BeautifulSoup) -> None:
        for node in soup.select("script, style, noscript, nav, footer, header, aside, form"):
            node.decompose()

    @staticmethod
    def _extract_meta(soup: BeautifulSoup) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for tag in soup.find_all("meta"):
            key = tag.get("property") or tag.get("name")
            value = tag.get("content")
            if key and value:
                result.setdefault(key.lower(), []).append(value.strip())
        return result

    @staticmethod
    def _meta_first(meta: dict[str, list[str]], key: str) -> str | None:
        values = meta.get(key.lower(), [])
        return values[0] if values else None

    @staticmethod
    def _meta_values(meta: dict[str, list[str]], key: str) -> list[str]:
        return meta.get(key.lower(), [])

    @staticmethod
    def _extract_json_ld(soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            nodes = payload if isinstance(payload, list) else [payload]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_type = node.get("@type", "")
                node_types = node_type if isinstance(node_type, list) else [node_type]
                if {str(item).lower() for item in node_types} & {"newsarticle", "article"}:
                    return node
        return {}

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str | None:
        candidates = soup.select("article, main, [itemprop='articleBody'], .article, .post, .content")
        if not candidates:
            candidates = [soup.body] if soup.body else [soup]

        best = ""
        for candidate in candidates:
            paragraphs = [p.get_text(" ", strip=True) for p in candidate.find_all(["p", "h2", "li"])]
            text = "\n".join(p for p in paragraphs if len(p) > 40)
            if len(text) > len(best):
                best = text
        return best or None

    @staticmethod
    def _extract_images(soup: BeautifulSoup, base_url: str) -> list[str]:
        urls: list[str] = []
        for image in soup.find_all("img"):
            src = image.get("src") or image.get("data-src") or image.get("data-original")
            if src:
                urls.append(urljoin(base_url, src))
        for source in soup.find_all("source"):
            srcset = source.get("srcset")
            if srcset:
                urls.append(urljoin(base_url, srcset.split()[0]))
        return GenericArticleParser._unique(urls)

    @staticmethod
    def _extract_counter(soup: BeautifulSoup, name: str) -> int | None:
        selectors = [f"[class*='{name}']", f"[data-{name}s]", f"[data-{name}-count]"]
        for node in soup.select(", ".join(selectors)):
            attrs = " ".join(str(value) for value in node.attrs.values()) if node.attrs else ""
            raw = " ".join([node.get_text(" ", strip=True), attrs])
            match = re.search(r"\d[\d\s.,]*", raw)
            if match:
                return int(re.sub(r"\D", "", match.group(0)))
        return None

    @staticmethod
    def _jsonld_value(payload: dict, key: str) -> str | None:
        value = payload.get(key)
        return value.strip() if isinstance(value, str) else None

    @staticmethod
    def _jsonld_author(payload: dict) -> str | None:
        author = payload.get("author") or payload.get("creator")
        if isinstance(author, dict):
            return author.get("name")
        if isinstance(author, list) and author:
            first = author[0]
            return first.get("name") if isinstance(first, dict) else str(first)
        return author if isinstance(author, str) else None

    @staticmethod
    def _jsonld_image(payload: dict) -> str | None:
        images = GenericArticleParser._jsonld_images(payload)
        return images[0] if images else None

    @staticmethod
    def _jsonld_images(payload: dict) -> list[str]:
        values: list[str] = []
        image = payload.get("image") or payload.get("associatedMedia")
        items = image if isinstance(image, list) else [image]
        for item in items:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                url = item.get("url") or item.get("image")
                if isinstance(url, str):
                    values.append(url)
        return GenericArticleParser._unique(values)

    @staticmethod
    def _jsonld_list(payload: dict, key: str) -> list[str]:
        value = payload.get(key)
        if isinstance(value, str):
            return GenericArticleParser._split_keywords(value)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _split_many(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            result.extend(GenericArticleParser._split_keywords(value))
        return result

    @staticmethod
    def _split_keywords(value: str | None) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]

    @staticmethod
    def _summarize(text: str | None) -> str | None:
        if not text:
            return None
        sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
        return sentence[:500]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result
