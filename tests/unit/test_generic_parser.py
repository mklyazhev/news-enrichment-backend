from src.services.parsing.generic import GenericArticleParser

import pytest


pytestmark = pytest.mark.unit


def test_generic_parser_extracts_article_data_from_multiple_sources() -> None:
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://cdn.example.com/main.jpg" />
        <meta name="author" content="Jane Reporter" />
        <meta name="keywords" content="economy, markets" />
        <meta name="description" content="Short article summary." />
        <script type="application/ld+json">
          {"@type": "NewsArticle", "keywords": ["finance"], "author": {"name": "LD Author"}}
        </script>
      </head>
      <body>
        <article>
          <p>Markets opened higher today as investors reacted to central bank comments and strong earnings reports.</p>
          <p>Analysts said the move could continue if inflation data remains stable during the next quarter.</p>
          <img src="/extra.jpg" />
          <div class="comments-count">17 comments</div>
        </article>
      </body>
    </html>
    """

    parsed = GenericArticleParser().parse_html(html, "https://news.example.com/story")

    assert parsed.author == "Jane Reporter"
    assert parsed.main_image_url == "https://cdn.example.com/main.jpg"
    assert "https://news.example.com/extra.jpg" in parsed.image_urls
    assert "economy" in parsed.tags
    assert "finance" in parsed.tags
    assert parsed.comments_count == 17
    assert parsed.summary == "Short article summary."
    assert parsed.full_text and "Markets opened higher" in parsed.full_text
