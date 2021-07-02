from logging import getLogger
from random import choices
from typing import Optional, cast
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import jwt
from redis import WatchError

from .config import Settings
from .game import init_game
from .main import redis_cli
from .models import GameConfig, GameConfigResponse
from .security import get_current_user, get_current_user_ws
from .utils import get_now_func

router = APIRouter()

settings = Settings()

logger = getLogger("uvicorn.error")


@router.post("/room")
def create():
    room_id = ""
    while room_id == "" or redis_cli.exists(f"{room_id}"):
        room_id = "".join(choices("123456789", k=6))
    redis_cli.hset(f"{room_id}", "state", 0)
    redis_cli.hset(f"{room_id}", "config", GameConfig().json())
    robby_clients[int(room_id)] = []
    return room_id


@router.post("/user/{room_id}")
async def enter(
    background: BackgroundTasks, room_id: int, user_name: str = Body(..., embed=True)
):
    if not redis_cli.exists(f"{room_id}"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are trying to enter a nonexistent room",
        )
    if has_started(room_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The game has been started"
        )

    with redis_cli.pipeline() as pipe:
        try:
            pipe.watch(f"{room_id}:members")

            if pipe.sismember(f"{room_id}:members", user_name):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Your name is already used in the room",
                )

            pipe.sadd(f"{room_id}:members", user_name)
        except WatchError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Some trouble happens, please retry",
            )

    user_id = str(uuid4())
    redis_cli.hset(user_id, "id", str(room_id))
    redis_cli.hset(user_id, "name", user_name)
    redis_cli.sadd(f"{room_id}:users", user_id)

    token = jwt.encode(
        {"sub": user_id}, settings.token_key, algorithm=settings.token_algo
    )

    background.add_task(broadcast_add_member, room_id, user_id, user_name)

    return token


def check_auth(room_id: int, user_id: str) -> bool:
    logger.info(f"[check_auth] user_id: {user_id}, room_id: {room_id}")
    return (r := redis_cli.hget(user_id, "id")) is not None and int(r) == room_id


def current_config(room_id: int) -> Optional[GameConfig]:
    if (c := redis_cli.hget(f"{room_id}", "config")) is not None:
        return GameConfig.parse_raw(c)
    else:
        return None


def current_members(room_id: int) -> list[str]:
    return list(redis_cli.smembers(f"{room_id}:members"))


@router.get("/room/{room_id}", response_model=GameConfigResponse)
def get_config(
    room_id: int,
    user_id: str = Depends(get_current_user),
):
    if not check_auth(room_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your operation is not allowed",
        )
    if (c := current_config(room_id)) is not None:
        return GameConfigResponse(game_config=c, members=current_members(room_id))
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The room does not exist",
        )


@router.patch("/room/{room_id}", response_model=GameConfig)
async def update_config(
    background: BackgroundTasks,
    room_id: int,
    game_config: GameConfig,
    user_id: str = Depends(get_current_user),
):
    if not check_auth(room_id, user_id) or has_started(room_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your operation is not allowed",
        )

    redis_cli.hset(f"{room_id}", "config", game_config.json())

    background.add_task(broadcast_update_config, room_id, game_config)

    return game_config


class RobbyClient:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def add_member(self, user_id: str, user_name: str):
        await self.websocket.send_json(
            {"op": "add_member", "user_id": user_id, "user_name": user_name}
        )

    async def delete_member(self, user_id: str):
        await self.websocket.send_json({"op": "delete_member", "user_id": user_id})

    async def update_config(self, game_config: GameConfig):
        await self.websocket.send_json({"op": "config", "config": game_config})

    async def start_game(self):
        await self.websocket.send_json({"op": "start"})


robby_clients: dict[int, list[RobbyClient]] = {}


async def broadcast_add_member(room_id: int, user_id: str, user_name: str):
    for client in robby_clients[room_id]:
        await client.add_member(user_id, user_name)


async def broadcast_delete_member(room_id: int, user_id: str):
    for client in robby_clients[room_id]:
        await client.delete_member(user_id)


async def broadcast_update_config(room_id: int, game_config: GameConfig):
    for client in robby_clients[room_id]:
        await client.update_config(game_config)


async def broadcast_start_game(room_id: int):
    for client in robby_clients[room_id]:
        await client.start_game()


def has_started(room_id: int) -> bool:
    """assumption: `room_id` exists in Redis"""
    room_state = int(cast(str, redis_cli.hget(f"{room_id}", "state")))
    return room_state == 1


@router.websocket("/room-ws/{room_id}")
async def room_ws(
    websocket: WebSocket,
    room_id: int,
    user_id: str = Depends(get_current_user_ws),
    get_now=Depends(get_now_func),
):
    if not check_auth(room_id, user_id):
        await websocket.close(status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    client = RobbyClient(websocket)
    robby_clients[room_id].append(client)

    try:
        while True:
            data = await websocket.receive_json()
            if has_started(room_id):
                continue

            if data["op"] == "start":
                with redis_cli.pipeline() as pipe:
                    try:
                        pipe.watch(f"{room_id}")
                        if pipe.hget(f"{room_id}", "state") == 0:
                            pipe.hset(f"{room_id}", "state", 1)
                            init_game(room_id, get_now)
                            await broadcast_start_game(room_id)
                    except WatchError:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Another user has already started the game",
                        )
    except WebSocketDisconnect:
        robby_clients[room_id].remove(client)

        if not has_started(room_id):
            user_name = cast(str, redis_cli.hget(user_id, "name"))
            redis_cli.srem(f"{room_id}:users", user_id)
            redis_cli.srem(f"{room_id}:members", user_name)
            redis_cli.delete(f"{user_id}")

            await broadcast_delete_member(room_id, user_id)

        await websocket.close()

        if len(robby_clients[room_id]) == 0:
            del robby_clients[room_id]
            redis_cli.delete(f"{room_id}")
