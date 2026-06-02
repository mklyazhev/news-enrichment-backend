from src.services.parsing.registry import SourceParserRegistry
from src.services.parsing.ria import RiaNewsParser

import pytest


pytestmark = pytest.mark.unit


def test_registry_selects_ria_parser_for_ria_domain() -> None:
    registry = SourceParserRegistry()

    assert isinstance(registry.source_parsers[0], RiaNewsParser)
    assert registry.source_parsers[0].supports("https://ria.ru/20260601/story.html")
    assert registry.source_parsers[0].supports("https://rsport.ria.ru/20260601/story.html")
    assert not registry.source_parsers[0].supports("https://example.com/story")
