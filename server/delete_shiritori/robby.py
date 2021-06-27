from random import choices
from typing import cast
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import jwt
from redis import Redis
from starlette.status import HTTP_403_FORBIDDEN

from .config import GameConfig, Settings
from .security import get_current_user, get_current_user_ws

router = APIRouter()

settings = Settings()

redis_cli = Redis(host="localhost", port=6379, db=0, decode_responses=True)


@router.post("/room")
def create():
    room_id = ""
    while room_id == "" or redis_cli.exists(room_id):
        room_id = "".join(choices("123456789", k=6))
    redis_cli.set(room_id, GameConfig().json())
    robby_clients[room_id] = []
    return room_id


@router.post("/user/{room_id}")
async def enter(background: BackgroundTasks, room_id: int, user_name: str):
    if has_started(room_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The game has been started"
        )

    user_id = str(uuid4())
    redis_cli.set(user_id, str(room_id))
    redis_cli.set(f"{user_id}:name", user_name)

    token = jwt.encode(
        {"sub": user_id}, settings.token_key, algorithm=settings.token_algo
    )

    background.add_task(broadcast_add_member, room_id, user_id, user_name)

    return token


def check_auth(room_id: int, user_id: str) -> bool:
    return (u := redis_cli.get(user_id)) is not None and int(u) == room_id


@router.patch("/room/{room_id}", response_model=GameConfig)
async def config(
    background: BackgroundTasks,
    room_id: int,
    game_config: GameConfig,
    user_id: str = Depends(get_current_user),
):
    if check_auth(room_id, user_id) or has_started(room_id):
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Your operation is not allowed"
        )

    redis_cli.set(str(room_id), game_config.json())

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
    game_config = GameConfig.parse_raw(cast(str, redis_cli.get(str(room_id))))
    return game_config.has_started


@router.websocket("/room-ws/{room_id}")
async def room_ws(
    websocket: WebSocket,
    background: BackgroundTasks,
    room_id: int,
    user_id: str = Depends(get_current_user_ws),
):
    if check_auth(room_id, user_id):
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
                game_config = GameConfig.parse_raw(
                    cast(str, redis_cli.get(str(room_id)))
                )
                game_config.has_started = True
                redis_cli.set(str(room_id), game_config.json())

                background.add_task(broadcast_start_game, room_id)
    except WebSocketDisconnect:
        if not has_started(room_id):
            background.add_task(broadcast_delete_member, room_id, user_id)

        await websocket.close()
        robby_clients[room_id].remove(client)

        if len(robby_clients[room_id]) == 0:
            del robby_clients[room_id]
