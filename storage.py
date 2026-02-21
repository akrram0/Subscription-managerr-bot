import json
import os

DATA_FILE = "data.json"


def load() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save(subs: list):
    with open(DATA_FILE, "w") as f:
        json.dump(subs, f, indent=2)


def next_id(subs: list) -> int:
    return max((s["id"] for s in subs), default=0) + 1


def add(name: str, price: float, period: str, date: str) -> dict:
    subs = load()
    sub = {"id": next_id(subs), "name": name, "price": price, "period": period, "date": date}
    subs.append(sub)
    save(subs)
    return sub


def get_all() -> list:
    return load()


def get_by_id(sub_id: int) -> dict | None:
    return next((s for s in load() if s["id"] == sub_id), None)


def delete(sub_id: int) -> bool:
    subs = load()
    new = [s for s in subs if s["id"] != sub_id]
    if len(new) == len(subs):
        return False
    save(new)
    return True


def update(sub_id: int, field: str, value) -> bool:
    subs = load()
    for s in subs:
        if s["id"] == sub_id:
            s[field] = value
            save(subs)
            return True
    return False


def due_in_days(days: int) -> list:
    from datetime import datetime, timedelta
    target = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    return [s for s in load() if s["date"] == target]
