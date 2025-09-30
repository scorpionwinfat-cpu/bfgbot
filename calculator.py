# --- Что фиксим этим файлом (calculator.py) ---
# Проблема: калькулятор открывался внешней ссылкой; в боте не было собственного расчёта с банками и условиями.
# Что должно заработать: внутренний модуль калькулятора с настраиваемыми ставками (rates.json), 
# нормализацией сроков и выдачей ТОП‑3 предложений по банкам. Можно менять ставки без правок кода.
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class Offer:
    bank: str
    rate: float     # годовая ставка (доля)
    fee: float      # комиссия (руб)
    base_fee: float # без агентской наценки
    min_fee: float

def _load_config(path: str = "rates.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _bucket_for_days(days: int) -> str:
    if days <= 90: return "<=90"
    if days <= 180: return "<=180"
    if days <= 365: return "<=365"
    return ">365"

def _fmt_money(x: float) -> str:
    s = f"{x:,.2f}".replace(",", " ").replace(".00", ".00")
    return s

def calculate(amount: float, days: int, gtype: str, prefer_bank: str | None = None, config_path: str = "rates.json") -> Tuple[List[Offer], Dict]:
    cfg = _load_config(config_path)
    banks = cfg.get("banks", {})
    agent_markup = float(cfg.get("agent_markup", 0.0))
    prorate_by_days = bool(cfg.get("prorate_by_days", True))
    round_to = int(cfg.get("round_to", 2))
    bucket = _bucket_for_days(days)
    gtype = gtype.strip().lower()

    offers: List[Offer] = []
    for bank, data in banks.items():
        if prefer_bank and bank != prefer_bank:
            continue
        types = data.get("types", {})
        if gtype not in types:
            continue
        rate_table = types[gtype]
        annual_rate = float(rate_table.get(bucket, 0.0))
        if annual_rate <= 0.0:
            continue

        min_fee = float(data.get("min_fee", 0.0))
        base_fee = amount * annual_rate * (days/365 if prorate_by_days else 1.0)
        fee = max(base_fee, min_fee)
        if agent_markup:
            fee = fee * (1.0 + agent_markup)

        fee = round(fee, round_to)
        base_fee = round(base_fee, round_to)
        offers.append(Offer(bank=bank, rate=annual_rate, fee=fee, base_fee=base_fee, min_fee=min_fee))

    offers.sort(key=lambda o: o.fee)
    meta = dict(bucket=bucket, agent_markup=agent_markup, prorate_by_days=prorate_by_days, round_to=round_to)
    return offers[:3], meta
