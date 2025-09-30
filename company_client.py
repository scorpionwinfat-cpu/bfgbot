# --- Что фиксим этим файлом (company_client.py) ---
# Проблема: в боте нет способа по ИНН получать карточку компании из внешнего источника («Зачестный бизнес»).
# Что должно заработать: универсальный клиент под API, настраиваемый через .env (ZCB_API_URL и ZCB_API_KEY),
# с аккуратным форматированием и устойчивым разбором данных (поля могут называться по‑разному).
#
# Пример .env:
#   ZCB_API_URL=https://api.zachestnyibiznes.ru/v2/companies?inn={inn}&key={key}
#   ZCB_API_KEY=ВАШ_КЛЮЧ
#
# Если у вас другой эндпоинт, достаточно указать корректный шаблон URL так, чтобы {inn} и {key} подставлялись.
# Клиент делает GET-запрос, кэширует ответы в файле cache_company.json и отдаёт словарь нормализованных полей.

import os
import json
import time
import requests
from typing import Dict, Any, Optional

ZCB_API_URL = os.getenv("ZCB_API_URL", "").strip()
ZCB_API_KEY = os.getenv("ZCB_API_KEY", "").strip()
CACHE_FILE = "cache_company.json"
CACHE_TTL = 12 * 60 * 60  # 12 часов

def _cache_load() -> Dict[str, Any]:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _cache_save(data: Dict[str, Any]) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _from_paths(d: Dict[str, Any], *paths, default: Optional[str] = "") -> Optional[str]:
    for p in paths:
        cur = d
        ok = True
        for key in p:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return default

def _normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], list) and payload["result"]:
        base = payload["result"][0]
    elif isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list) and payload["items"]:
        base = payload["items"][0]
    else:
        base = payload

    def g(*paths, default=""):
        return _from_paths(base, *paths, default=default)

    name = g(("name",), ("company","name"), ("full_name",), ("Наименование",))
    short_name = g(("short_name",), ("company","short_name"))
    inn = g(("inn",), ("company","inn"), ("ИНН",))
    ogrn = g(("ogrn",), ("company","ogrn"), ("ОГРН",))
    kpp = g(("kpp",), ("company","kpp"), ("КПП",))
    okved = g(("okved",), ("company","okved"), ("ОКВЭД",))
    address = g(("address",), ("company","address"), ("Адрес",), ("factual_address",))
    status = g(("status",), ("company","status"), ("Статус",))
    ceo = g(("ceo",), ("company","ceo"), ("director",), ("Руководитель",), ("management","name"))
    reg_date = g(("registration_date",), ("company","registration_date"), ("ДатаРегистрации",), ("egrul","reg_date"))
    employees = g(("employees",), ("company","employees_count"), ("Численность",))
    revenue = g(("revenue",), ("fin","revenue"), ("Выручка",))
    profit = g(("profit",), ("fin","profit"), ("Прибыль",))

    return {
        "name": name or short_name or "(без названия)",
        "short_name": short_name or "",
        "inn": inn or "",
        "ogrn": ogrn or "",
        "kpp": kpp or "",
        "okved": okved or "",
        "address": address or "",
        "status": status or "",
        "ceo": ceo or "",
        "reg_date": reg_date or "",
        "employees": employees or "",
        "revenue": revenue or "",
        "profit": profit or "",
        "raw": base,
    }

def fetch_company_by_inn(inn: str) -> Optional[Dict[str, Any]]:
    if not ZCB_API_URL:
        raise RuntimeError("ZCB_API_URL is empty. Set it in .env")
    if "{inn}" not in ZCB_API_URL:
        raise RuntimeError("ZCB_API_URL must contain {inn} placeholder")
    url = ZCB_API_URL.replace("{inn}", inn)
    if "{key}" in url:
        url = url.replace("{key}", ZCB_API_KEY)

    cache = _cache_load()
    now = time.time()
    if inn in cache and (now - cache[inn].get("_ts", 0)) < CACHE_TTL:
        return cache[inn].get("data")

    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and data.get("error") and not data.get("result"):
        raise RuntimeError(f"Provider error: {data.get('error')}")

    norm = _normalize(data) if data else None
    cache[inn] = {"_ts": now, "data": norm}
    _cache_save(cache)
    return norm
