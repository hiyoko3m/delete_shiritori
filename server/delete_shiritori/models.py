from pydantic import BaseModel


class GameConfig(BaseModel):
    has_started: bool = False
    init_time: int = 300  # unit: second


class GameConfigResponse(BaseModel):
    members: list[str] = []
    game_config: GameConfig


class RemainTimes(BaseModel):
    remain_times: list[int] = []  # unit: second


class PersonalGameState(BaseModel):
    remain_time: int  # unit: second
    used_char_flag: int = 0  # 45 bits (a ka sa ta na ha ma ya3 ra wa nn)
