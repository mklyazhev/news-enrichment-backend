from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.models.news import JobStatus


class NewsCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=255)
    source_url: HttpUrl
    published_at: datetime | None = None
    teaser: str | None = None


class NewsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    published_at: datetime | None = None
    teaser: str | None = None


class NewsRead(BaseModel):
    id: int
    title: str
    source: str
    source_url: str
    published_at: datetime | None
    teaser: str | None
    full_text: str | None
    main_image_url: str | None
    image_urls: list[str]
    categories: list[str]
    tags: list[str]
    author: str | None
    views_count: int | None
    comments_count: int | None
    keywords: list[str]
    summary: str | None
    region: str | None
    topic: str | None
    has_video: bool
    parser_version: str | None
    enriched_at: datetime | None
    enrichment_error: str | None

    model_config = ConfigDict(from_attributes=True)


class NewsList(BaseModel):
    items: list[NewsRead]
    total: int
    limit: int
    offset: int


class EnrichmentRequest(BaseModel):
    news_ids: list[int] | None = Field(default=None, description="Explicit news ids to enrich")
    source: str | None = Field(default=None, description="Enrich not-yet-enriched news from one source")
    only_missing: bool = True
    limit: int = Field(default=100, ge=1, le=1000)


class EnrichmentJobRead(BaseModel):
    id: int
    status: JobStatus
    criteria: dict
    requested_count: int
    processed_count: int
    failed_count: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str
