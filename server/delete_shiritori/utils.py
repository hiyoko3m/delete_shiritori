from datetime import datetime, timezone


def get_now_func():
    return lambda: datetime.isoformat(datetime.now(timezone.utc))
