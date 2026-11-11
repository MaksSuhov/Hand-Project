from fastapi import FastAPI

from app.api.routes.chat_router import router as chat_router

app = FastAPI(title="Hand Project v 0.1.0")

app.include_router(router=chat_router)

@app.get('/health')
async def health() -> str:
    return "все нормас"