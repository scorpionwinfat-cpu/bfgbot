# --- Что фиксим этим файлом (bitrix_client.py) ---
# Проблема: после последнего обновления пропал вывод поля «Плановая дата».
# Причина: поле не передавалось в select и не форматировалось в ответе.
# Что должно заработать: «Плановая дата» снова отображается (формат ДД.ММ.ГГГГ), 
# настраиваемое через .env (BITRIX_UF_PLANNED), плюс прежние улучшения сохраняются.
import os
import requests
from typing import Optional, Dict, List
from datetime import datetime

BITRIX_DOMAIN = os.getenv("BITRIX_DOMAIN", "").strip()
BITRIX_REST_PATH = (os.getenv("BITRIX_REST_PATH", "") or os.getenv("BITRIX_WEBHOOK", "")).strip()

UF_INN_FIELD = os.getenv("BITRIX_UF_INN", "UF_CRM_5785BA746B0E4")      # ИНН
UF_NUM_FIELD = os.getenv("BITRIX_UF_NUMBER", "UF_CRM_57747F824D6FA")   # № гарантии/закупки
UF_DUE_FIELD = os.getenv("BITRIX_UF_DUE", "UF_CRM_1468381658")         # Срок действия БГ (дата)
UF_PLANNED_FIELD = os.getenv("BITRIX_UF_PLANNED", "UF_CRM_1468380196") # Плановая дата (дата)

_STAGE_CACHE: Dict[str, Dict[str, str]] = {}

def _base_url() -> str:
    d = BITRIX_DOMAIN.replace("https://", "").replace("http://", "").rstrip("/")
    p = BITRIX_REST_PATH.strip("/")
    if not d or not p:
        raise RuntimeError("BITRIX_DOMAIN or BITRIX_REST_PATH is not set in .env")
    return f"https://{d}/rest/{p}"

def _call(method: str, params: Dict) -> Dict:
    url = f"{_base_url()}/{method}.json"
    r = requests.post(url, data=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Bitrix error: {data}")
    return data

def _fmt_date(value: Optional[str], with_time: bool = False) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y")
    except Exception:
        try:
            dt = datetime.strptime(value[:10], "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return value

def _load_stage_names(category_id: str) -> Dict[str, str]:
    names: Dict[str, str] = {}
    cat = str(category_id or "0")
    try:
        r = _call("crm.dealcategory.stage.list", {"id": int(cat)})
        for st in r.get("result", []):
            sid = st.get("STATUS_ID") or st.get("ID"); name = st.get("NAME")
            if sid and name: names[sid] = name
        if names: return names
    except Exception: pass
    try:
        r = _call("crm.status.list", {"filter[ENTITY_ID]": f"DEAL_STAGE_{cat}"})
        for st in r.get("result", []):
            sid = st.get("STATUS_ID"); name = st.get("NAME")
            if sid and name: names[sid] = name
        if names: return names
    except Exception: pass
    if cat in ("0", 0, "", None):
        try:
            r = _call("crm.status.list", {"filter[ENTITY_ID]": "DEAL_STAGE"})
            for st in r.get("result", []):
                sid = st.get("STATUS_ID"); name = st.get("NAME")
                if sid and name: names[sid] = name
        except Exception: pass
    return names

def _stage_name(category_id: str, stage_id: str) -> str:
    if not stage_id: return "нет данных"
    cat = str(category_id or "0")
    cache = _STAGE_CACHE.get(cat)
    if cache is None:
        cache = _load_stage_names(cat)
        _STAGE_CACHE[cat] = cache
    return cache.get(stage_id, stage_id)

def _format_deal(result: Dict) -> str:
    title = result.get("TITLE") or "(без названия)"
    deal_id = result.get("ID", "")
    category_id = str(result.get("CATEGORY_ID", "0"))
    stage_id = result.get("STAGE_ID", "")
    stage = _stage_name(category_id, stage_id)
    created = _fmt_date(result.get("DATE_CREATE"), with_time=True)
    guarantee_sum = result.get("UF_CRM_5DDDE2A9DE5D1") or ""
    guarantee_number = result.get(UF_NUM_FIELD) or ""
    guarantee_due = _fmt_date(result.get(UF_DUE_FIELD))
    planned_date = _fmt_date(result.get(UF_PLANNED_FIELD))

    parts = [
        f"Сделка #{deal_id}: «{title}»",
        f"Стадия: {stage}",
        f"Создана: {created}",
    ]
    if guarantee_sum: parts.append(f"Сумма БГ: {guarantee_sum}")
    if guarantee_number: parts.append(f"Номер: {guarantee_number}")
    if guarantee_due: parts.append(f"Срок действия БГ: {guarantee_due}")
    if planned_date: parts.append(f"Плановая дата: {planned_date}")
    return "\n".join(parts)

def _select_fields() -> List[str]:
    return ["ID","TITLE","STAGE_ID","DATE_CREATE","CATEGORY_ID",
            UF_NUM_FIELD, UF_DUE_FIELD, UF_PLANNED_FIELD]

def deal_get(deal_id: str) -> Optional[Dict]:
    try:
        d = _call("crm.deal.get", {"ID": deal_id})
        return d.get("result") or None
    except Exception:
        return None

def lead_get(lead_id: str) -> Optional[Dict]:
    try:
        d = _call("crm.lead.get", {"ID": lead_id})
        return d.get("result") or None
    except Exception:
        return None

def deals_by_inn(inn: str, limit: int = 10) -> List[Dict]:
    try:
        d = _call("crm.deal.list", {
            f"filter[{UF_INN_FIELD}]": inn,
            "order[DATE_CREATE]": "DESC",
            **{f"select[{i}]": fld for i, fld in enumerate(_select_fields())}
        })
        return d.get("result", [])[:limit]
    except Exception:
        return []

def get_due_date_from_deal(deal_id: str) -> Optional[str]:
    d = deal_get(deal_id)
    if not d: return None
    raw = d.get(UF_DUE_FIELD)
    if not raw: return None
    try:
        if "T" in raw: return raw[:10]
        datetime.strptime(raw[:10], "%Y-%m-%d")
        return raw[:10]
    except Exception:
        return None

def get_status_by_number(number: str) -> Optional[str]:
    d = deal_get(number)
    if d: return _format_deal(d)
    l = lead_get(number)
    if l:
        created = _fmt_date(l.get("DATE_CREATE"), with_time=True)
        return f"Лид #{l.get('ID')}: «{l.get('TITLE') or '(без названия)'}»\nСтатус: {l.get('STATUS_ID')}\nСоздан: {created}"
    try:
        dd = _call("crm.deal.list", {
            f"filter[{UF_NUM_FIELD}]": number,
            **{f"select[{i}]": fld for i, fld in enumerate(_select_fields())}
        }).get("result", [])
        if dd: return _format_deal(dd[0])
    except Exception: pass
    try:
        dd = _call("crm.deal.list", {
            "filter[TITLE]": number,
            **{f"select[{i}]": fld for i, fld in enumerate(_select_fields())}
        }).get("result", [])
        if dd: return _format_deal(dd[0])
    except Exception: pass
    return None
