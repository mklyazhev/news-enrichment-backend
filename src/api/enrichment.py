from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.models.news import EnrichmentJob
from src.schemas.news import EnrichmentJobRead, EnrichmentRequest
from src.services.enrichment import create_enrichment_job, submit_enrichment_job

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.post("/jobs", response_model=EnrichmentJobRead, status_code=status.HTTP_202_ACCEPTED)
async def start_job(
    payload: EnrichmentRequest,
    db: AsyncSession = Depends(get_session),
) -> EnrichmentJob:
    job = await create_enrichment_job(db, payload)
    submit_enrichment_job(job.id)
    return job


@router.get("/jobs/{job_id}", response_model=EnrichmentJobRead)
async def get_job(job_id: int, db: AsyncSession = Depends(get_session)) -> EnrichmentJob:
    job = await db.get(EnrichmentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job
