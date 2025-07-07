# FastAPI NLP Service

This service handles all heavy-duty Natural Language Processing (NLP) for the LiMao project. Its sole responsibility is to receive requests to process new media, perform a vocabulary frequency analysis, and populate the database.

## Local Setup & Installation

1.  **Clone the repository:**

    ```bash
    git clone github.com/yunz-dev/limao
    cd limao/server
    ```

2.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the server:**

    ```bash
    fastapi dev main.py
    ```

    The server will be available at `http://127.0.0.1:8000`.

## API Endpoints

### Health

  * **Endpoint**: `GET /health`
  * **Description**: Checks status of Server
  * **Status Code**: `200 Success`
  * **Returns**: status `ok` on success

### Start a Processing Job

  * **Endpoint**: `POST /v1/process`
  * **Description**: Receives a media file reference and queues it for NLP analysis. The analysis runs as a background task.
  * **Status Code**: `202 Accepted`
  * **Returns**: A job ID and initial status.

### Check Job Status

  * **Endpoint**: `GET /v1/process/status/{job_id}`
  * **Description**: Checks the status of a previously submitted analysis job.
  * **Returns**: The current status of the job (e.g., `pending`, `processing`, `completed`, `failed`).
