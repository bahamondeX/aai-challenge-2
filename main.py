import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api import route

load_dotenv()
AAI_API_KEY = os.environ["AAI_API_KEY"]

app = FastAPI(
    title="Youtube Translator",
    description="Translate Youtube videos into different languages",
    version="0.1.0"
)

app.include_router(route())

app.mount("/", StaticFiles(directory="dist", html=True), name="static")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse("dist/index.html")