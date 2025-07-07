from time import sleep

job_db = {}


def run_nlp_analysis(job_id: str, media_id: str, storage_path: str):
    """
    A placeholder for your actual, time-consuming NLP analysis.
    This function runs in the background.
    """
    print(f"Starting analysis for job_id: {job_id} on media: {media_id}")
    job_db[job_id] = {"status": "processing", "media_id": media_id}

    # 1. Download file from storage_path
    # 2. Perform NLP (parsing, tokenizing, counting)
    sleep(15)  # Simulate a 15-second processing time

    # 3. Save results to your main Supabase database
    # 4. Update the final job status
    job_db[job_id]["status"] = "completed"
    print(f"Finished analysis for job_id: {job_id}")
