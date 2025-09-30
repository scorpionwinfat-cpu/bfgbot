# --- Что фиксим этим файлом (storage.py) ---
# Проблема: не было нормальной авторизации по ИНН и привязки напоминаний к пользователю.
# Что должно заработать: хранение ИНН в профиле пользователя, быстрые геттеры/сеттеры,
# удобное добавление напоминаний. Совместимо с прежним data.json.
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

DATA_FILE = Path("data.json")

def _load() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {"users": {}, "reminders": []}
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: Dict[str, Any]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_user(user_id: int, name_or_inn: str) -> None:
    data = _load()
    user = data["users"].get(str(user_id), {"id": user_id})
    # попытаемся распознать ИНН (10–12 цифр)
    inn = name_or_inn if name_or_inn.isdigit() and 9 < len(name_or_inn) < 13 else user.get("inn", "")
    user.update({"id": user_id, "display": name_or_inn, "inn": inn})
    data["users"][str(user_id)] = user
    _save(data)

def set_user_inn(user_id: int, inn: str) -> None:
    data = _load()
    user = data["users"].get(str(user_id), {"id": user_id})
    user["inn"] = inn
    data["users"][str(user_id)] = user
    _save(data)

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    data = _load()
    return data["users"].get(str(user_id))

def add_reminder(user_id: int, guarantee_number: str, due_date: str, offsets_days: List[int]) -> None:
    """due_date format YYYY-MM-DD"""
    data = _load()
    for offset in offsets_days:
        from datetime import datetime, timedelta
        remind_on = (datetime.fromisoformat(due_date) - timedelta(days=offset)).date().isoformat()
        data["reminders"].append({
            "user_id": user_id,
            "guarantee_number": guarantee_number,
            "due_date": due_date,
            "offset_days": offset,
            "remind_on": remind_on,
            "sent": False
        })
    _save(data)

def due_reminders_today(today: Optional[str] = None) -> list:
    data = _load()
    if today is None:
        from datetime import datetime
        today = datetime.now().date().isoformat()
    return [r for r in data["reminders"] if r["remind_on"] == today and not r["sent"]]

def mark_reminder_sent(rem) -> None:
    data = _load()
    for r in data["reminders"]:
        if (r["user_id"] == rem["user_id"] and r["guarantee_number"] == rem["guarantee_number"]
            and r["remind_on"] == rem["remind_on"] and r["offset_days"] == rem["offset_days"]):
            r["sent"] = True
            break
    _save(data)
