from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.models.news import NewsArticle
from src.schemas.news import NewsCreate, NewsList, NewsRead, NewsUpdate

router = APIRouter(prefix="/news", tags=["news"])


@router.post("", response_model=NewsRead, status_code=status.HTTP_201_CREATED)
async def create_news(payload: NewsCreate, db: AsyncSession = Depends(get_session)) -> NewsArticle:
    article_data = payload.model_dump()
    article_data["source_url"] = str(article_data["source_url"])
    article = NewsArticle(**article_data)
    db.add(article)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="news with this source_url already exists") from exc
    await db.refresh(article)
    return article


@router.get("", response_model=NewsList)
async def list_news(
    db: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, description="Search in title, teaser, full text and summary"),
    source: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    enriched: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NewsList:
    statement = select(NewsArticle)
    count_statement = select(func.count()).select_from(NewsArticle)

    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                NewsArticle.title.ilike(pattern),
                NewsArticle.teaser.ilike(pattern),
                NewsArticle.full_text.ilike(pattern),
                NewsArticle.summary.ilike(pattern),
            )
        )
    if source:
        filters.append(NewsArticle.source == source)
    if category:
        filters.append(
            text(
                "EXISTS ("
                "SELECT 1 FROM json_array_elements_text(news_articles.categories) AS category_item(value) "
                "WHERE category_item.value = :category_filter"
                ")"
            ).bindparams(category_filter=category)
        )
    if tag:
        filters.append(
            text(
                "EXISTS ("
                "SELECT 1 FROM json_array_elements_text(news_articles.tags) AS tag_item(value) "
                "WHERE tag_item.value = :tag_filter"
                ")"
            ).bindparams(tag_filter=tag)
        )
    if author:
        filters.append(NewsArticle.author == author)
    if enriched is not None:
        filters.append(
            NewsArticle.enriched_at.is_not(None) if enriched else NewsArticle.enriched_at.is_(None)
        )

    for filter_ in filters:
        statement = statement.where(filter_)
        count_statement = count_statement.where(filter_)

    total = await db.scalar(count_statement) or 0
    page_statement = (
        statement.order_by(NewsArticle.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.scalars(page_statement)).all())
    return NewsList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{news_id}", response_model=NewsRead)
async def get_news(news_id: int, db: AsyncSession = Depends(get_session)) -> NewsArticle:
    article = await db.get(NewsArticle, news_id)
    if not article:
        raise HTTPException(status_code=404, detail="news not found")
    return article


@router.patch("/{news_id}", response_model=NewsRead)
async def update_news(
    news_id: int,
    payload: NewsUpdate,
    db: AsyncSession = Depends(get_session),
) -> NewsArticle:
    article = await db.get(NewsArticle, news_id)
    if not article:
        raise HTTPException(status_code=404, detail="news not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(article, key, value)
    await db.commit()
    await db.refresh(article)
    return article
