from fastapi import FastAPI

app = FastAPI(
    title="Distributed Multi-Agent Storytelling Cloud",
    version="0.1.0",
    description="API foundation for a consistency-aware distributed storytelling system.",
)


@app.get("/health", tags=["Operations"])
async def health():
    return {
        "status": "healthy",
        "service": "storytelling-api",
        "version": "0.1.0",
    }
