from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from redis import Redis

from .config import Settings
from .robby import router as robby_router

app = FastAPI()

app.mount("/client", StaticFiles(directory="client"), name="client")


settings = Settings()

redis_cli = Redis(
    host="localhost",
    password=settings.redis_pass,
    port=6379,
    db=0,
    decode_responses=True,
)


@app.get("/")
def index():
    return RedirectResponse("/client")


app.include_router(robby_router)

#
#
# @app.get("/game/{room_id}")
# def game_state(room_id: int):
#    return ""
#
#
# @app.websocket("/game-ws/{room_id}")
# def game_ws(room_id: int):
#    return ""
#
#
# @app.post("/word/{room_id}")
# def answer(room_id: int):
#    return ""
#
#
# @app.get("/time/{target_user_token}")
# def remaining_time(target_user_token: int):
#    return ""
