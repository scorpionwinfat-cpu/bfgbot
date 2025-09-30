# Copilot Instructions for BFG Bot

## Overview
This is a simple MVP Telegram bot for Baikal Finance Group, built with aiogram v3. The bot provides commands for registration, status checking, reminders, calculations, and help. Data is stored in a local `data.json` file. Bitrix24 integration is stubbed for now.

## Key Components
- `main.py`: Entry point. Handles bot setup, command routing, and main logic.
- `storage.py`: Handles reading/writing reminders to `data.json`.
- `config.py`: Loads configuration (e.g., tokens, settings).
- `data.json`: Stores reminders and user data.
- `bitrix_client.py` (if present): Stub for Bitrix24 integration. Replace `get_status_by_number` with real API calls when ready.

## Developer Workflows
- **Setup:**
  - Use Python 3.10+ and create a virtual environment.
  - Install dependencies with `pip install -r requirements.txt`.
  - Copy `.env.example` to `.env` and set `BOT_TOKEN`.
- **Run Locally:**
  - `python main.py`
- **Testing:**
  - No formal test suite detected. Add tests as needed (e.g., `test_*.py`).
- **Reminders:**
  - Reminders are stored in `data.json` and checked daily while the process runs. For production, migrate to a database and use a scheduler.

## Project-Specific Patterns
- **Command Handlers:**
  - Each command (e.g., `/start`, `/status`, `/reminder`, `/calc`, `/help`) is implemented as a handler in `main.py`.
- **Reminders Format:**
  - Use a single-line format: `REM:ГАРАНТИЯ=1234;СРОК=2026-08-15;ОФФСЕТЫ=30,7`.
- **Bitrix24 Integration:**
  - Stubbed in `bitrix_client.py`. Replace with real API logic as needed.
- **Data Storage:**
  - All persistent data is in `data.json`. No database by default.

## Conventions
- Russian is used for user-facing messages and some comments.
- Minimal error handling; expand as needed for production.
- For production, use webhooks and a persistent server.

## Examples
- To add a reminder, send `/reminder` and follow the prompt. Data is saved in `data.json`.
- To check status, send `/status` and enter a number. The response is stubbed.

## References
- See `README.md` for setup and usage details.
- See `main.py` for command logic and flow.
- See `storage.py` for data persistence patterns.

---

If you add new commands or integrations, update this file and the README accordingly.