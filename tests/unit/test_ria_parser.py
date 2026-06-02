from src.services.parsing.generic import GenericArticleParser
from src.services.parsing.ria import RIA_PARSER_VERSION, RiaNewsParser

import pytest


pytestmark = pytest.mark.unit


def test_ria_parser_extracts_real_article_fixture(ria_html: str) -> None:
    parser = RiaNewsParser(GenericArticleParser())
    parsed = parser.parse_html(ria_html, "https://ria.ru/20260531/polnolunie-2095779946.html")

    assert parsed.parser_version == RIA_PARSER_VERSION
    assert parsed.author == "Дарья Буймова"
    assert parsed.full_text and "МОСКВА, 31 мая - РИА Новости" in parsed.full_text
    assert parsed.main_image_url and parsed.main_image_url.startswith("https://cdnn21.img.ria.ru/images/")
    assert parsed.image_urls
    assert "Наука" in parsed.categories
    assert "Луна" in parsed.tags
    assert "Российская академия наук" in parsed.tags
    assert parsed.summary and "Второе полнолуние мая" in parsed.summary
    assert parsed.region == "Луна"
    assert parsed.topic == "Наука"
    assert parsed.has_video is False
