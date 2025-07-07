from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    """Defines the response sent back immediately after a job is started."""

    job_id: str = Field(..., description="The unique ID for this processing task.")
    status: str = Field(default="pending", description="The initial status of the job.")
