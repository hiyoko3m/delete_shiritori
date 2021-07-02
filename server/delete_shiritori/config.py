from pydantic import BaseSettings


class Settings(BaseSettings):
    token_key: str = "dummy"
    token_algo: str = "HS256"
    token_ex: int = 120

    redis_pass: str = "dummy"
