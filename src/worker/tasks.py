import asyncio

from celery.utils.log import get_task_logger

from src.db.session import engine
from src.services.enrichment import run_enrichment_job
from src.worker.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    name="news_enrichment.run_enrichment_job",
)
def run_enrichment_job_task(self, job_id: int) -> None:
    logger.info("Starting enrichment job %s", job_id)
    asyncio.run(_run_enrichment_job_task(job_id))


async def _run_enrichment_job_task(job_id: int) -> None:
    try:
        await run_enrichment_job(job_id)
    finally:
        await engine.dispose()
