# --- Что фиксим этим файлом (main.py) ---
# Новое: команда /org — карточка компании по ИНН через Monitoring (add-id -> card).
# Плюс отладочная /orgraw (если нужно увидеть сырой JSON).
# Сохранены прежние команды: /auth, /mydeals, /status, /reminder, /calc (фикс шага суммы).
#
# Рядом должны лежать: config.py, storage.py, bitrix_client.py, calculator.py, rates.json, zcb_client.py
# Требуется: aiogram v3, requests

import re, json, asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import BOT_TOKEN
import storage, bitrix_client, calculator, zcb_client

dp = Dispatcher()
STATE = {}

def _set(uid: int, **kwargs):
    st = STATE.get(uid) or {}; st.update(kwargs); STATE[uid] = st
def _get(uid: int, key: str, default=None):
    return (STATE.get(uid) or {}).get(key, default)
def _clear(uid: int): STATE.pop(uid, None)
def _fmt_money(x: float) -> str: return f"{x:,.2f}".replace(",", " ")

# ----------------- Старт/Хелп -----------------
@dp.message(Command("start"))
async def cmd_start(m: Message):
    _clear(m.from_user.id)
    await m.answer("Здравствуйте! Доступно: /auth /mydeals /status /reminder /calc /org /orgraw /help.")

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("/auth /mydeals /status /reminder /calc /org /orgraw")

# ----------------- AUTH -----------------
@dp.message(Command("auth"))
async def cmd_auth(m: Message):
    _set(m.from_user.id, mode="await_inn")
    await m.answer("Введите ваш ИНН (10–12 цифр).")

@dp.message(F.text.regexp(r"^\d{10,12}$") & F.func(lambda m: _get(m.from_user.id, "mode")=="await_inn"))
async def on_inn(m: Message):
    storage.set_user_inn(m.from_user.id, m.text.strip())
    _clear(m.from_user.id)
    await m.answer("ИНН сохранён.")

# ----------------- MYDEALS -----------------
@dp.message(Command("mydeals"))
async def cmd_mydeals(m: Message):
    user = storage.get_user(m.from_user.id) or {}; inn = user.get("inn")
    if not inn:
        await m.answer("Сначала /auth и ИНН."); return
    deals = bitrix_client.deals_by_inn(inn, limit=10)
    if not deals:
        await m.answer("Сделок не найдено."); return
    lines = []
    for d in deals:
        title = d.get("TITLE") or "(без названия)"; did = d.get("ID")
        stage = bitrix_client._stage_name(d.get("CATEGORY_ID","0"), d.get("STAGE_ID",""))
        created = bitrix_client._fmt_date(d.get("DATE_CREATE"), with_time=True)
        lines.append(f"#{did} — {title}\nСтадия: {stage}\nСоздана: {created}")
    await m.answer("Ваши сделки:\n\n" + "\n\n".join(lines))

# ----------------- STATUS -----------------
@dp.message(Command("status"))
async def cmd_status(m: Message):
    _set(m.from_user.id, mode="await_status")
    await m.answer("Введите ID/номер.")

@dp.message(F.text.regexp(r"^\d+$") & F.func(lambda m: _get(m.from_user.id, "mode")=="await_status"))
async def on_status(m: Message):
    status = bitrix_client.get_status_by_number(m.text.strip())
    await m.answer(status or "Не нашёл по номеру.")
    _clear(m.from_user.id)

# ----------------- REMINDER -----------------
@dp.message(Command("reminder"))
async def cmd_reminder(m: Message):
    _set(m.from_user.id, mode="await_reminder_id")
    await m.answer("Пример: 20520 45,10")

@dp.message(F.text.regexp(r"^\d+\s+\d+(?:,\d+)*$") & F.func(lambda m: _get(m.from_user.id, "mode")=="await_reminder_id"))
async def reminder_with_offsets(m: Message):
    deal_id, offsets = m.text.strip().split(None, 1)
    offsets_list = [int(x) for x in offsets.split(",") if x.isdigit()]
    await _set_reminder_from_deal(m, deal_id, offsets_list)

@dp.message(F.text.regexp(r"^\d+$") & F.func(lambda m: _get(m.from_user.id, "mode")=="await_reminder_id"))
async def reminder_id_only(m: Message):
    await _set_reminder_from_deal(m, m.text.strip(), [30,7])

async def _set_reminder_from_deal(m: Message, deal_id: str, offsets: list[int]):
    due = bitrix_client.get_due_date_from_deal(deal_id)
    if not due:
        await m.answer("В сделке нет срока БГ."); _clear(m.from_user.id); return
    d = bitrix_client.deal_get(deal_id); number = (d or {}).get(bitrix_client.UF_NUM_FIELD,"") or deal_id
    storage.add_reminder(m.from_user.id, str(number), due, offsets)
    await m.answer(f"Напомню по #{deal_id} (№ {number}) — за {', '.join(map(str,offsets))} дн.")
    _clear(m.from_user.id)

# ----------------- CALC -----------------
@dp.message(Command("calc"))
async def calc_start(m: Message):
    _set(m.from_user.id, mode="calc_type")
    await m.answer("Калькулятор: тендер / исполнение / аванс?")

@dp.message(F.text.lower().in_({"тендер","исполнение","аванс"}) & F.func(lambda m: _get(m.from_user.id,"mode")=="calc_type"))
async def calc_type(m: Message):
    _set(m.from_user.id, mode="calc_amount", gtype=m.text.strip().lower())
    await m.answer("Сумма гарантии (цифрами):")

@dp.message(F.text & F.func(lambda m: _get(m.from_user.id,"mode")=="calc_amount"))
async def calc_amount(m: Message):
    digits = re.sub(r"\D+","", m.text)
    if len(digits) < 5 or len(digits) > 15:
        await m.answer("Введите сумму (5–15 цифр)."); return
    _set(m.from_user.id, mode="calc_days", amount=float(digits))
    await m.answer("Срок в днях:")

@dp.message(F.text & F.func(lambda m: _get(m.from_user.id,"mode")=="calc_days"))
async def calc_days(m: Message):
    digits = re.sub(r"\D+","", m.text)
    if not digits:
        await m.answer("Введите срок, напр. 90")
        return
    _set(m.from_user.id, mode="calc_bank", days=int(digits))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Лучшее предложение", callback_data="bank:best"),
        InlineKeyboardButton(text="Выбрать банк", callback_data="bank:choose"),
    ]])
    await m.answer("Выберите банк или лучшее предложение.", reply_markup=kb)

@dp.callback_query(F.data.startswith("bank:"))
async def calc_bank_choice(cb: CallbackQuery):
    uid = cb.from_user.id
    if _get(uid,"mode")!="calc_bank":
        await cb.answer(); return
    action = cb.data.split(":",1)[1]
    if action=="best":
        await _compute_and_show(cb.message, None)
    else:
        import json
        try:
            with open("rates.json","r",encoding="utf-8") as f:
                data = json.load(f)
            banks = list((data.get("banks") or {}).keys())
        except Exception:
            banks = []
        rows = []
        for i in range(0,len(banks),2):
            row = [InlineKeyboardButton(text=b, callback_data=f"selbank:{b}") for b in banks[i:i+2]]
            if row: rows.append(row)
        if rows:
            await cb.message.answer("Выберите банк:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        else:
            await cb.message.answer("Список банков пуст. Заполните rates.json.")
    await cb.answer()

@dp.callback_query(F.data.startswith("selbank:"))
async def calc_bank_selected(cb: CallbackQuery):
    await _compute_and_show(cb.message, cb.data.split(":",1)[1])
    await cb.answer()

async def _compute_and_show(message: Message, prefer_bank: str | None):
    uid = message.chat.id
    gtype = _get(uid,"gtype"); amount = _get(uid,"amount"); days = _get(uid,"days")
    if not all([gtype,amount,days]):
        await message.answer("Данных не хватает, /calc заново."); _clear(uid); return
    offers, meta = calculator.calculate(amount=amount, days=days, gtype=gtype, prefer_bank=prefer_bank, config_path="rates.json")
    if not offers:
        await message.answer("Нет предложений. Проверьте rates.json."); _clear(uid); return
    def fmt(x: float): return f"{x:,.2f}".replace(","," ")
    lines = [f"Тип: {gtype}, Сумма: {fmt(amount)} ₽, Срок: {days} дн. (корзина {meta['bucket']})"]
    for i,o in enumerate(offers,1):
        lines.append(f"{i}) {o.bank} — {o.rate*100:.2f}% → {fmt(o.fee)} ₽ (расчёт: {fmt(o.base_fee)} ₽, минимум: {fmt(o.min_fee)} ₽)")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Новый расчёт", callback_data="calc:new"),
        InlineKeyboardButton(text="Изменить банк", callback_data="bank:choose"),
    ]])
    await message.answer("Расчёт по ставкам (rates.json):\n" + "\n".join(lines), reply_markup=kb)
    _clear(uid)

@dp.callback_query(F.data=="calc:new")
async def calc_new(cb: CallbackQuery):
    _clear(cb.from_user.id); await calc_start(cb.message); await cb.answer()

# ----------------- ORG (Monitoring add-id -> card) -----------------
@dp.message(Command("org"))
async def org_start(m: Message):
    _set(m.from_user.id, mode="await_org_inn")
    await m.answer("Введите ИНН (10 или 12 цифр).")

@dp.message(F.text.regexp(r"^\d{10,12}$") & F.func(lambda m: _get(m.from_user.id,"mode")=="await_org_inn"))
async def org_by_inn(m: Message):
    inn = m.text.strip()
    try:
        info = zcb_client.ensure_added_then_card(inn)
    except Exception as e:
        await m.answer(f"Ошибка запроса: {e}"); _clear(m.from_user.id); return
    parts = [f"Компания по ИНН {inn}"]
    if info.get("name"): parts.append(f"Наименование: {info['name']}")
    if info.get("ogrn"): parts.append(f"ОГРН: {info['ogrn']}")
    if info.get("kpp"): parts.append(f"КПП: {info['kpp']}")
    if info.get("status"): parts.append(f"Статус: {info['status']}")
    if info.get("address"): parts.append(f"Адрес: {info['address']}")
    if info.get("okved"): parts.append(f"ОКВЭД: {info['okved']}")
    await m.answer("\n".join(parts)); _clear(m.from_user.id)

# ----------------- ORGRAW (диагностика) -----------------
@dp.message(Command("orgraw"))
async def orgraw_start(m: Message):
    _set(m.from_user.id, mode="await_orgraw_inn")
    await m.answer("Введите ИНН для отладки (10 или 12).")

@dp.message(F.text.regexp(r"^\d{10,12}$") & F.func(lambda m: _get(m.from_user.id,"mode")=="await_orgraw_inn"))
async def orgraw_by_inn(m: Message):
    inn = m.text.strip()
    try:
        info = zcb_client.ensure_added_then_card(inn)
    except Exception as e:
        await m.answer(f"Ошибка запроса: {e}"); _clear(m.from_user.id); return
    raw = info.get("raw") or {}
    snippet = json.dumps(raw, ensure_ascii=False)[:800]
    await m.answer(
        f"Ключевые поля:\n"
        f"name: {info.get('name')}\ninn: {info.get('inn')}\nogrn: {info.get('ogrn')}\n"
        f"kpp: {info.get('kpp')}\nstatus: {info.get('status')}\naddress: {info.get('address')}\nokved: {info.get('okved')}\n\n"
        f"RAW (фрагмент):\n{snippet}"
    )
    _clear(m.from_user.id)

# ----------------- Цифры вне режимов -----------------
@dp.message(F.text.regexp(r"^\d+$") & ~F.func(lambda m: _get(m.from_user.id,"mode") in {"await_inn","await_status","await_reminder_id","calc_amount","calc_days","calc_bank","calc_type","await_org_inn","await_orgraw_inn"}))
async def general_digits(m: Message):
    status = bitrix_client.get_status_by_number(m.text.strip())
    await m.answer(status or "Команда не распознана. Используйте /status или /calc.")

# ----------------- Доставка напоминаний -----------------
async def reminder_daemon(bot: Bot):
    while True:
        for rem in storage.due_reminders_today():
            try:
                await bot.send_message(
                    chat_id=rem["user_id"],
                    text=f"Напоминание по гарантии №{rem['guarantee_number']}. Срок: {rem['due_date']}. Осталось {rem['offset_days']} дн."
                )
                storage.mark_reminder_sent(rem)
            except Exception:
                pass
        await asyncio.sleep(60)

# ----------------- Точка входа -----------------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Set it in .env")
    bot = Bot(BOT_TOKEN, parse_mode=None)
    asyncio.create_task(reminder_daemon(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())