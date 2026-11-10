from fastapi import FastAPI

app = FastAPI(description="Hand Project v 0.1.0")

@app.get('/health')
async def health() -> str:
    return "все нормас"