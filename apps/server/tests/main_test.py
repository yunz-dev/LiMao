from fastapi.testclient import TestClient
from main import app  # Import your FastAPI app instance

# Create a test client
client = TestClient(app)


def test_health():
    """
    Tests that the /health endpoint returns a 200 OK status
    and the expected JSON response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
