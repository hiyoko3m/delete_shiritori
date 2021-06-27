from pydantic import BaseSettings, BaseModel


class Settings(BaseSettings):
    token_key: str = "dummy"
    token_algo: str = "HS256"
    token_ex: int = 120


class GameConfig(BaseModel):
    has_started: bool = False
