from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.services.parsing.base import ArticleParser, ParsedArticle
from src.services.parsing.generic import GenericArticleParser

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

        full_text = self._extract_ria_text(soup) or generic.full_text
        images = GenericArticleParser._unique(self._extract_ria_images(soup, base_url) + generic.image_urls)
        tags = GenericArticleParser._unique(self._extract_ria_tags(soup) + generic.tags)
        categories = GenericArticleParser._unique(self._extract_ria_categories(soup) + generic.categories)
        author = self._text_or_none(soup.select_one(".article__author, .article__authors")) or generic.author

        return ParsedArticle(
            full_text=full_text,
            main_image_url=generic.main_image_url or (images[0] if images else None),
            image_urls=images,
            categories=categories,
            tags=tags,
            author=author,
            views_count=generic.views_count,
            comments_count=generic.comments_count,
            keywords=generic.keywords,
            summary=generic.summary,
            region=generic.region,
            topic=categories[0] if categories else generic.topic,
            has_video=generic.has_video or bool(soup.select(".article__video, video, iframe")),
            parser_version=RIA_PARSER_VERSION,
        )

    @staticmethod
    def _extract_ria_text(soup: BeautifulSoup) -> str | None:
        blocks = soup.select(".article__body .article__text, .article__text, [data-type='text']")
        paragraphs = [block.get_text(" ", strip=True) for block in blocks]
        text = "\n".join(paragraph for paragraph in paragraphs if len(paragraph) > 30)
        return text or None

    @staticmethod
    def _extract_ria_images(soup: BeautifulSoup, base_url: str) -> list[str]:
        return GenericArticleParser._extract_images(soup, base_url)

    @staticmethod
    def _extract_ria_tags(soup: BeautifulSoup) -> list[str]:
        nodes = soup.select(".article__tags a, .tags__item, a[href*='/tags/']")
        return GenericArticleParser._unique([node.get_text(" ", strip=True) for node in nodes])

    @staticmethod
    def _extract_ria_categories(soup: BeautifulSoup) -> list[str]:
        nodes = soup.select(".article__rubric, .breadcrumbs a, a[href*='/category_']")
        return GenericArticleParser._unique([node.get_text(" ", strip=True) for node in nodes])

    @staticmethod
    def _text_or_none(node) -> str | None:
        if not node:
            return None
        text = node.get_text(" ", strip=True)
        return text or None
