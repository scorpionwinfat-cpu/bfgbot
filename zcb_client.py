# --- Что фиксим этим файлом (zcb_client.py v2) ---
# Проблема: /monitoring/data/card возвращает поля в разных схемах, и простого доступа по 1-2 ключам недостаточно.
# Что должно заработать: более «умный» парсер с РЕКУРСИВНЫМ поиском ключей по синонимам (рус/англ),
# чтобы вытаскивать name/inn/ogrn/kpp/status/address/okved из любой разумной структуры.
#
# API: monitoring/add-id -> monitoring/card (id = ИНН/ОГРН/ОГРНИП/ИННФЛ)
# Требуется: requests

import os
import re
import requests
from typing import Dict, Any, Iterable

API_KEY = os.getenv("ZCB_API_KEY", "").strip()
ADD_ID_URL = os.getenv("ZCB_MON_ADD_ID_URL",
    "https://zachestnyibiznesapi.ru/monitoring/data/add-id?id={id}&api_key={key}"
).strip()
CARD_URL = os.getenv("ZCB_MON_CARD_URL",
    "https://zachestnyibiznesapi.ru/monitoring/data/card?id={id}&api_key={key}"
).strip()

class ZCBError(Exception):
    pass

def _get_json(url: str) -> Dict[str, Any]:
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and str(data.get("status")) not in {"200", "0", "OK", "ok"} and not data.get("body"):
        raise ZCBError(f"{data.get('status')}: {data.get('message') or data}")
    return data

def _walk(d: Any) -> Iterable[tuple[str, Any]]:
    """Генератор (ключ, значение) по всему дереву словаря/списка, ключ — путь через точки."""
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                for kk, vv in _walk(v):
                    yield f"{k}.{kk}", vv
            yield k, v
    elif isinstance(d, list):
        for i, v in enumerate(d):
            if isinstance(v, (dict, list)):
                for kk, vv in _walk(v):
                    yield f"[{i}].{kk}", vv
            yield f"[{i}]", v

def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [part for part in (_stringify_value(v) for v in value) if part]
        return " ".join(parts)
    if isinstance(value, dict):
        lower_keys = {k.lower(): v for k, v in value.items()}
        fio_parts: list[str] = []
        fio_key_groups = (
            ("last", "surname", "family", "last_name"),
            ("first", "name", "given", "first_name"),
            ("middle", "patronymic", "mid", "middle_name"),
        )
        for group in fio_key_groups:
            for key in group:
                if key in lower_keys:
                    part = _stringify_value(lower_keys[key])
                    if part:
                        fio_parts.append(part)
                    break
        if fio_parts:
            return " ".join(fio_parts)
        # fallback: склеим все строковые значения словаря
        return " ".join(
            part for part in (_stringify_value(v) for v in value.values()) if part
        )
    return ""


def _find_first(body: Dict[str, Any], key_variants: Iterable[str]) -> str:
    """Ищем значение по набору синонимов ключей (регистронезависимо), проходим глубоко."""
    low_map = {}
    for k, v in _walk(body):
        low_map[k.lower()] = v
    for pat in key_variants:
        key = pat.lower()
        # точное совпадение
        if key in low_map:
            val = _stringify_value(low_map[key])
            if val:
                return val
        # частичное (ключ содержит слово), чтобы поймать, например, egrul.name.full
        for k, v in low_map.items():
            if key in k:
                val = _stringify_value(v)
                if val:
                    return val
    return ""

NAME_KEYS    = ["НаимЮЛПолн", "Наименование", "name", "full_name", "egrul.name.full", "egrul_name", "НаимПолн"]
NAME_KEYS.extend(
    [
        "egrip.fio.full",
        "egrip.fio",
        "egrip.name.full",
        "ФИОПолн",
        "ФИО",
        "fio.full",
        "fio_full",
        "fio.full_name",
        "fio.fullname",
        "fio",
    ]
)
INN_KEYS     = ["ИНН", "inn"]
OGRN_KEYS    = ["ОГРН", "ogrn"]
KPP_KEYS     = ["КПП", "kpp"]
STATUS_KEYS  = ["Статус", "status", "egrul.status"]
ADDRESS_KEYS = ["АдресПолн", "Адрес", "address", "addr", "egrul.address"]
OKVED_KEYS   = ["ОКВЭДОснКод", "okved", "ОКВЭД", "egrul.okved.main.code"]

def ensure_added_then_card(inn: str) -> Dict[str, Any]:
    if not API_KEY:
        raise ZCBError("ZCB_API_KEY не задан в .env")
    if not inn or not inn.isdigit() or len(inn) not in (10, 12):
        raise ZCBError("Некорректный ИНН")

    add_url = ADD_ID_URL.replace("{id}", inn).replace("{key}", API_KEY)
    _get_json(add_url)  # ok if 200/ok

    card_url = CARD_URL.replace("{id}", inn).replace("{key}", API_KEY)
    obj = _get_json(card_url)
    body = obj.get("body") or obj

    name = _find_first(body, NAME_KEYS)
    innv = _find_first(body, INN_KEYS) or inn
    ogrn = _find_first(body, OGRN_KEYS)
    kpp  = _find_first(body, KPP_KEYS)
    status = _find_first(body, STATUS_KEYS)
    address = _find_first(body, ADDRESS_KEYS)
    okved = _find_first(body, OKVED_KEYS)

    # косметика: удалить лишние пробелы/переводы
    def clean(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    normalized = {
        "name": clean(name) if name else "(без названия)",
        "inn": clean(innv) if innv else inn,
        "ogrn": clean(ogrn),
        "kpp":  clean(kpp),
        "status": clean(status),
        "address": clean(address),
        "okved": clean(okved),
        "raw": body,
    }
    return normalized
