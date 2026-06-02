from pathlib import Path

import pytest


@pytest.fixture
def ria_html() -> str:
    return Path("tests/fixtures/ria.html").read_text(encoding="utf-8")
