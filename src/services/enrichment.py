from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import get_settings
from src.db.session import async_session_maker
from src.models.news import EnrichmentJob, JobStatus, NewsArticle
from src.schemas.news import EnrichmentRequest
from src.services.parsing.registry import SourceParserRegistry

settings = get_settings()


async def select_news_for_enrichment(db: AsyncSession, request: EnrichmentRequest) -> list[NewsArticle]:
    statement: Select[tuple[NewsArticle]] = select(NewsArticle)
    if request.news_ids:
        statement = statement.where(NewsArticle.id.in_(request.news_ids))
    if request.source:
        statement = statement.where(NewsArticle.source == request.source)
    if request.only_missing:
        statement = statement.where(NewsArticle.enriched_at.is_(None))
    statement = statement.limit(request.limit)
    return list((await db.scalars(statement)).all())


async def create_enrichment_job(db: AsyncSession, request: EnrichmentRequest) -> EnrichmentJob:
    articles = await select_news_for_enrichment(db, request)
    job = EnrichmentJob(
        status=JobStatus.queued,
        criteria=request.model_dump(exclude_none=True),
        requested_count=len(articles),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def submit_enrichment_job(job_id: int) -> None:
    from src.worker.tasks import run_enrichment_job_task

    run_enrichment_job_task.delay(job_id)


async def run_enrichment_job(job_id: int) -> None:
    async with async_session_maker() as db:
        try:
            job = await db.get(EnrichmentJob, job_id)
            if not job:
                return
            job.status = JobStatus.running
            job.started_at = datetime.now(UTC)
            await db.commit()

            request = EnrichmentRequest(**job.criteria)
            articles = await select_news_for_enrichment(db, request)
            parser_registry = SourceParserRegistry(settings.http_timeout_seconds, settings.http_max_retries)

            for article in articles:
                try:
                    parsed = await parser_registry.fetch_and_parse(article.source_url)
                    article.full_text = parsed.full_text
                    article.main_image_url = parsed.main_image_url
                    article.image_urls = parsed.image_urls
                    article.categories = parsed.categories
                    article.tags = parsed.tags
                    article.author = parsed.author
                    article.views_count = parsed.views_count
                    article.comments_count = parsed.comments_count
                    article.keywords = parsed.keywords
                    article.summary = parsed.summary
                    article.region = parsed.region
                    article.topic = parsed.topic
                    article.has_video = parsed.has_video
                    article.parser_version = parsed.parser_version
                    article.enrichment_error = None
                    article.enriched_at = datetime.now(UTC)
                    job.processed_count += 1
                except Exception as exc:  # noqa: BLE001
                    article.enrichment_error = str(exc)
                    job.failed_count += 1
                finally:
                    await db.commit()

            job.status = JobStatus.completed if job.failed_count == 0 else JobStatus.failed
            job.finished_at = datetime.now(UTC)
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            job = await db.get(EnrichmentJob, job_id)
            if job:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.finished_at = datetime.now(UTC)
                await db.commit()
