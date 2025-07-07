from fastapi import FastAPI
from routers import process

app = FastAPI(title="LiMao Docs", version="0.1.0", description="API for LiMao Server")

app.include_router(
    process.router, prefix="/v1/process", tags=["Natural Language Processing"]
)


@app.get("/health", tags=["Monitoring"])
async def root():
    """
    For monitoring status of server
    """
    return {"status": "ok"}
