from collections import Counter
import re

from nltk.corpus import stopwords


def load_stop_words() -> set[str]:
    try:
        return set(stopwords.words("russian")) | set(stopwords.words("english"))
    except LookupError as exc:
        raise RuntimeError(
            "NLTK stopwords corpus is required. "
            "Install it with: python -m nltk.downloader stopwords"
        ) from exc


STOP_WORDS = load_stop_words()


def fallback_keywords_from_text(text: str | None, limit: int = 10) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", text.lower())
    common = Counter(word for word in words if word not in STOP_WORDS).most_common(limit)
    return [word for word, _ in common]
