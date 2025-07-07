import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from models.job_response import JobResponse
from models.process_request import ProcessRequest
from services.nlp import job_db, run_nlp_analysis

router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=202)
def process_media_endpoint(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Receives a request to process media, adds the job to the background,
    and immediately returns a job ID.
    """
    # Generate a unique ID for this specific processing job.
    job_id = str(uuid.uuid4())
    job_db[job_id] = {"status": "pending"}

    # Add the heavy-lifting function to run in the background.
    # The client does NOT have to wait for run_nlp_analysis to finish.
    background_tasks.add_task(
        run_nlp_analysis, job_id, request.media_id, request.storage_path
    )

    # Immediately return the job ID to the client.
    return {"job_id": job_id, "status": "pending"}


@router.get("/status/{job_id}")
def get_job_status_endpoint(job_id: str):
    """
    Checks the status of a previously submitted job using its job ID.
    """
    # Find the job in our temporary database.
    job = job_db.get(job_id)

    if not job:
        # If no job is found, raise a 404 Not Found error.
        raise HTTPException(status_code=404, detail="Job not found")

    # Return the current status of the job.
    return {"job_id": job_id, "status": job.get("status")}
