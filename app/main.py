from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router  
from app.infrastructure.observability.tracing import init_tracing, shutdown_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing()
    yield
    shutdown_tracing()


app = FastAPI(title="Hand Project v 0.1.0", lifespan=lifespan)

app.include_router(router=api_router)

@app.get('/health')
async def health() -> str:
    return "все нормас"