from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import uvicorn

from config import get_settings
from database import connect_to_mongodb, close_mongodb_connection, check_db_health
from routers import ingest, chat, auth, projects, conversations, studio, graph

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongodb()
    yield
    # Shutdown
    await close_mongodb_connection()

app = FastAPI(
    title="Multi-Source AI Tutor",
    description="Cross-source conflict detection, multi-source learning projects, and persistent tutoring API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all: always return JSON, never a raw HTML 500 page.
    """
    tb = traceback.format_exc()
    print(f"[ERROR] Unhandled exception on {request.method} {request.url}:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{type(exc).__name__}: {str(exc)}",
            "path": str(request.url),
        },
    )

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(studio.router, prefix="/api", tags=["studio"])
app.include_router(graph.router)



@app.get("/health")
async def health():
    db_ok = await check_db_health()
    return {
        "status": "ok",
        "database": "connected" if db_ok else "unavailable",
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
