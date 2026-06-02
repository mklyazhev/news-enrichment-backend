from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedArticle:
    full_text: str | None = None
    main_image_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str | None = None
    views_count: int | None = None
    comments_count: int | None = None
    keywords: list[str] = field(default_factory=list)
    summary: str | None = None
    region: str | None = None
    topic: str | None = None
    has_video: bool = False
    parser_version: str = "unknown"


class ArticleParser(ABC):
    @abstractmethod
    async def fetch_and_parse(self, url: str) -> ParsedArticle:
        raise NotImplementedError

    @abstractmethod
    def parse_html(self, html: str, base_url: str) -> ParsedArticle:
        raise NotImplementedError
