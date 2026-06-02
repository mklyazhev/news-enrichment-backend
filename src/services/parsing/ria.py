from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.services.parsing.base import ArticleParser, ParsedArticle
from src.services.parsing.generic import GenericArticleParser
from src.services.parsing.keywords import fallback_keywords_from_text

RIA_PARSER_VERSION = "ria-news-v1"


class RiaNewsParser(ArticleParser):
    def __init__(self, generic_parser: GenericArticleParser) -> None:
        self.generic_parser = generic_parser

    @staticmethod
    def supports(url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return hostname == "ria.ru" or hostname.endswith(".ria.ru")

    async def fetch_and_parse(self, url: str) -> ParsedArticle:
        html = await self.generic_parser.fetch_html(url)
        return self.parse_html(html, base_url=url)

    def parse_html(self, html: str, base_url: str) -> ParsedArticle:
        generic = self.generic_parser.parse_html(html, base_url)
        soup = BeautifulSoup(html, "lxml")
        json_ld = GenericArticleParser._extract_json_ld(soup)
        meta = GenericArticleParser._extract_meta(soup)

        full_text = self._extract_ria_text(soup) or generic.full_text
        jsonld_images = GenericArticleParser._jsonld_images(json_ld)
        images = GenericArticleParser._unique(
            jsonld_images
            + self._extract_ria_images(soup, base_url)
            + generic.image_urls
        )
        tags = GenericArticleParser._unique(
            self._extract_ria_tags(soup)
            + GenericArticleParser._meta_values(meta, "article:tag")
            + GenericArticleParser._jsonld_list(json_ld, "keywords")
            + generic.tags
        )
        categories = GenericArticleParser._unique(
            GenericArticleParser._jsonld_list(json_ld, "articleSection")
            + GenericArticleParser._meta_values(meta, "article:section")
            + self._extract_ria_categories(soup)
            + generic.categories
        )
        author = (
            self._text_or_none(soup.select_one(".article__author, .article__authors"))
            or GenericArticleParser._jsonld_author(json_ld)
            or GenericArticleParser._meta_first(meta, "article:author")
            or generic.author
        )
        summary = (
            GenericArticleParser._jsonld_value(json_ld, "description")
            or GenericArticleParser._meta_first(meta, "description")
            or GenericArticleParser._meta_first(meta, "og:description")
            or generic.summary
        )

        return ParsedArticle(
            full_text=full_text,
            main_image_url=images[0] if images else generic.main_image_url,
            image_urls=images,
            categories=categories,
            tags=tags,
            author=author,
            views_count=generic.views_count,
            comments_count=generic.comments_count,
            keywords=GenericArticleParser._unique(tags + categories + fallback_keywords_from_text(full_text))[:10],
            summary=summary,
            region=self._extract_region(json_ld),
            topic=categories[0] if categories else generic.topic,
            has_video=generic.has_video or bool(soup.select(".article__video, [data-video], video, iframe")),
            parser_version=RIA_PARSER_VERSION,
        )

    @staticmethod
    def _extract_ria_text(soup: BeautifulSoup) -> str | None:
        blocks = soup.select(".article__body .article__text, .article__text")
        paragraphs = [block.get_text(" ", strip=True) for block in blocks]
        text = "\n".join(paragraph for paragraph in paragraphs if len(paragraph) > 30)
        return text or None

    @staticmethod
    def _extract_ria_images(soup: BeautifulSoup, base_url: str) -> list[str]:
        selectors = ".photoview__open img, .article__media img, .article__photo img, picture img"
        urls: list[str] = []
        for image in soup.select(selectors):
            src = image.get("src") or image.get("data-src") or image.get("data-original")
            if src:
                urls.append(urljoin(base_url, src))
        return GenericArticleParser._unique(urls)

    @staticmethod
    def _extract_ria_tags(soup: BeautifulSoup) -> list[str]:
        nodes = soup.select(".article__tags a, .tags__item, a[href*='/tags/']")
        tags = [node.get_text(" ", strip=True) for node in nodes]
        return [tag for tag in GenericArticleParser._unique(tags) if tag.lower() not in {"теги", "tags"}]

    @staticmethod
    def _extract_ria_categories(soup: BeautifulSoup) -> list[str]:
        nodes = soup.select(".article__rubric, .breadcrumbs a, a[href*='/category_']")
        return GenericArticleParser._unique([node.get_text(" ", strip=True) for node in nodes])

    @staticmethod
    def _extract_region(json_ld: dict) -> str | None:
        content_location = json_ld.get("contentLocation")
        if isinstance(content_location, str):
            return content_location
        if isinstance(content_location, list) and content_location:
            return str(content_location[0])
        return None

    @staticmethod
    def _text_or_none(node) -> str | None:
        if not node:
            return None
        text = node.get_text(" ", strip=True)
        return text or None
