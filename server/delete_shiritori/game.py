from typing import cast

from fastapi import status
from fastapi.exceptions import HTTPException

from .config import Settings
from .main import redis_cli
from .models import GameConfig

settings = Settings()


def init_game(room_id: int, get_now):
    config_raw = redis_cli.hget(f"{room_id}", "config")
    if config_raw is None or not redis_cli.exists(f"{room_id}:users"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified room does not exist",
        )

    n = redis_cli.scard(f"{room_id}:users")
    users = redis_cli.srandmember(f"{room_id}:users", n)

    redis_cli.hset(f"{room_id}", "turn", users[0])

    game_config = GameConfig.parse_raw(config_raw)
    for user_id in users:
        user_id = cast(str, user_id)
        redis_cli.hset(user_id, "state", 0)
        redis_cli.hset(user_id, "time", game_config.init_time)
        redis_cli.hset(user_id, "since", get_now())
