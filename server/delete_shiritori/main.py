from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/client", StaticFiles(directory="client"), name="client")


@app.get("/", response_class=HTMLResponse)
async def index():
    return "a"
