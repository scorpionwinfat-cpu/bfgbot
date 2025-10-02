# scripts/smoke.py
# Проверка: secrets на месте, Telegram getMe работает, ZCB monitoring/card отвечает 200.

import os
import sys
import json
import urllib.parse
import urllib.request

def getenv_strict(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"[SMOKE] Missing required env: {name}")
        sys.exit(2)
    return val

def http_get_json(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "BFG-CI/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        print(f"[SMOKE] Non-JSON at {url[:120]}... got {data[:200]!r}")
        sys.exit(3)

def main():
    bot_token = getenv_strict("BOT_TOKEN")
    zcb_key   = getenv_strict("ZCB_API_KEY")
    # Bitrix переменные тоже проверим, но без реальных вызовов:
    getenv_strict("BITRIX_DOMAIN")
    getenv_strict("BITRIX_REST_PATH")

    # 1) Telegram getMe
    tg_url = f"https://api.telegram.org/bot{bot_token}/getMe"
    tg = http_get_json(tg_url)
    if not tg.get("ok"):
        print("[SMOKE] Telegram getMe failed:", tg)
        sys.exit(4)
    print("[SMOKE] Telegram getMe OK")

    # 2) ZCB monitoring/card (ИНН публичный пример)
    inn = "2724079827"
    zcb_url = f"https://zachestnyibiznesapi.ru/monitoring/data/card?id={urllib.parse.quote(inn)}&api_key={urllib.parse.quote(zcb_key)}"
    zcb = http_get_json(zcb_url)
    # У ЗаЧБ "status": "200" при успехе
    status = str(zcb.get("status", ""))
    if status != "200":
        print("[SMOKE] ZCB card bad status:", status, zcb.get("message"))
        sys.exit(5)
    print("[SMOKE] ZCB monitoring/card OK")

    print("[SMOKE] All checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
