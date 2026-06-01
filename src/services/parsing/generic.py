import asyncio
import json
import re
from collections import Counter
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.services.parsing.base import ArticleParser, ParsedArticle

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
            self._split_keywords(meta.get("article:tag"))
            + self._split_keywords(meta.get("keywords"))
            + self._jsonld_list(json_ld, "keywords")
        )

        summary = meta.get("description") or self._jsonld_value(json_ld, "description") or self._summarize(text)
        main_image = meta.get("og:image") or self._jsonld_image(json_ld) or (images[0] if images else None)
        categories = self._unique(
            self._split_keywords(meta.get("article:section"))
            + self._split_keywords(meta.get("section"))
            + self._split_keywords(meta.get("category"))
        )

        return ParsedArticle(
            full_text=text,
            main_image_url=main_image,
            image_urls=images,
            categories=categories,
            tags=tags,
            author=meta.get("author") or self._jsonld_author(json_ld),
            views_count=self._extract_counter(soup, "view"),
            comments_count=self._extract_counter(soup, "comment"),
            keywords=self._keywords(text, tags),
            summary=summary,
            region=meta.get("geo.placename") or meta.get("region"),
            topic=categories[0] if categories else None,
            has_video=bool(soup.select("video, iframe[src*='youtube'], iframe[src*='rutube'], iframe[src*='vimeo']")),
            parser_version=PARSER_VERSION,
        )

    @staticmethod
    def _remove_noise(soup: BeautifulSoup) -> None:
        for node in soup.select("script, style, noscript, nav, footer, header, aside, form"):
            node.decompose()

    @staticmethod
    def _extract_meta(soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            key = tag.get("property") or tag.get("name")
            value = tag.get("content")
            if key and value:
                result[key.lower()] = value.strip()
        return result

    @staticmethod
    def _extract_json_ld(soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            nodes = payload if isinstance(payload, list) else [payload]
            for node in nodes:
                if isinstance(node, dict) and str(node.get("@type", "")).lower() in {"newsarticle", "article"}:
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
        author = payload.get("author")
        if isinstance(author, dict):
            return author.get("name")
        if isinstance(author, list) and author and isinstance(author[0], dict):
            return author[0].get("name")
        return author if isinstance(author, str) else None

    @staticmethod
    def _jsonld_image(payload: dict) -> str | None:
        image = payload.get("image")
        if isinstance(image, str):
            return image
        if isinstance(image, list) and image:
            return image[0] if isinstance(image[0], str) else image[0].get("url")
        if isinstance(image, dict):
            return image.get("url")
        return None

    @staticmethod
    def _jsonld_list(payload: dict, key: str) -> list[str]:
        value = payload.get(key)
        if isinstance(value, str):
            return GenericArticleParser._split_keywords(value)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _split_keywords(value: str | None) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]

    @staticmethod
    def _keywords(text: str | None, fallback: list[str]) -> list[str]:
        if not text:
            return fallback[:10]
        words = re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", text.lower())
        stop_words = {"который", "которая", "после", "также", "about", "there", "their", "these", "would"}
        common = Counter(word for word in words if word not in stop_words).most_common(10)
        return GenericArticleParser._unique(fallback + [word for word, _ in common])[:10]

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
