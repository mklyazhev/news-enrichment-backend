from src.services.parsing.base import ArticleParser, ParsedArticle
from src.services.parsing.generic import GenericArticleParser
from src.services.parsing.ria import RiaNewsParser


class SourceParserRegistry:
    def __init__(self, timeout_seconds: float = 10, max_retries: int = 2) -> None:
        self.generic_parser = GenericArticleParser(timeout_seconds, max_retries)
        self.source_parsers: list[ArticleParser] = [
            RiaNewsParser(self.generic_parser),
        ]

    async def fetch_and_parse(self, url: str) -> ParsedArticle:
        for parser in self.source_parsers:
            if parser.supports(url):
                return await parser.fetch_and_parse(url)
        return await self.generic_parser.fetch_and_parse(url)
