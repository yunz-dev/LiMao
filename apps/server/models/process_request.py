from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Defines the expected request body for starting a process job."""

    media_id: str = Field(
        ..., description="The unique ID for the media item from the database."
    )
    storage_path: str = Field(..., description="Path to the file in Supabase Storage.")
    language: str = Field(
        ..., description="The language of the media file (e.g., 'korean')."
    )
