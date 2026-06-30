# Telegram Digest Bot

> A self-hosted Telegram assistant that reads your **unread** group and forum
> messages and turns them into clean, AI-generated summaries — on demand or as an
> automatic daily digest.

[![CI](https://github.com/TmInfinity/telegram-digest-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/TmInfinity/telegram-digest-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)

Stop scrolling through hundreds of unread messages. Pick a group, choose a summary
style, and get the gist in seconds — in **English, Turkish, Russian, or Turkmen**.

---

## Why a userbot?

Telegram **bots cannot read group history** they aren't actively involved in. So this
project pairs two identities that run in the same event loop:

| Identity | Library | Role |
|---|---|---|
| **Userbot** (your own account) | [Telethon](https://docs.telethon.dev) | *Reads* your unread messages |
| **Bot** (a BotFather bot) | [python-telegram-bot](https://python-telegram-bot.org) | *Talks* to you (commands, buttons, delivery) |
| **AI** | [OpenRouter](https://openrouter.ai) (OpenAI-compatible) | Summarizes the messages |

Because it drives your *own* account, this is a **personal, self-hosted tool** — you
run your own copy with your own credentials. See [SECURITY.md](SECURITY.md).

## Features

- 📋 **On-demand summaries** (`/ozet`) — lists groups/forum topics with unread
  messages, then summarizes the one you pick.
- 🎛️ **Three summary modes** — General, Knowledge & tips, Action items & tasks. Each
  summary offers one-tap buttons to re-run in another mode.
- 📰 **Automatic daily digest** (`/otomatik`) — every morning at 09:00, summarizes the
  last 24h of selected groups/topics and marks them read. Includes a **sleep
  catch-up**: if your machine is asleep at 09:00, it runs as soon as it wakes.
- 🧵 **Forum-aware** — handles supergroup forum topics correctly (per-topic unread
  tracking and read receipts).
- 📄 **Q&A export** — extract a group owner's unanswered/answered messages into a
  Markdown file with embedded images.
- 🌍 **4 languages** — English, Turkish, Russian, Turkmen. Both the interface **and**
  the AI summaries follow your chosen language. Switch any time with `/dil`.
- 🎨 **Polished UX** — bold section headers, collapsible long summaries, TL;DR lines,
  inline action buttons, remembered last-used mode.
- 🔒 **Owner-only** — every command and button is locked to your chat id.

## Tech stack

Python 3.13 · Telethon · python-telegram-bot · httpx · OpenRouter · `uv` for env
management · `launchd` for background scheduling on macOS.

## Quick start

### 1. Prerequisites
- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/)
- A Telegram account, a bot from [@BotFather](https://t.me/BotFather), and an
  [OpenRouter](https://openrouter.ai/keys) API key.

### 2. Install
```bash
git clone https://github.com/TmInfinity/telegram-digest-bot.git
cd telegram-digest-bot
uv sync
```

### 3. Configure
```bash
cp .env.example .env
chmod 600 .env
# then edit .env with your own values
```
Need your numeric chat id? Send `/start` to your bot, then run:
```bash
uv run python chatid_bul.py
```

### 4. Run
```bash
uv run python bot.py
```
On first run, Telethon asks for your phone number and a login code, then creates
`ozet_session.session` (keep this file private — it is account-level access).

### 5. (Optional) Run 24/7 on macOS
A ready-to-edit `launchd` template lives in
[`deploy/com.telegram-digest.plist.example`](deploy/com.telegram-digest.plist.example) —
follow the comments inside it.

## Commands

| Command | Description |
|---|---|
| `/ozet` | List unread groups → pick group/topic → pick mode → get summary |
| `/otomatik` | Configure & toggle the automatic daily digest |
| `/dil` | Change the language (English / Türkçe / Русский / Türkmençe) |
| `/durum` | Bot status (uptime, selected groups, active model) |
| `/start` | Welcome / help |

## Configuration & persistence

- `.env` — secrets (git-ignored). Template in `.env.example`.
- `ozet_session.session` — Telethon session (**account access — never share**).
- `ayarlar.json` — runtime settings (auto-digest on/off, selected groups/topics,
  language, last mode). Created automatically.
- `app.log` — rotating operational log.

## Documentation

Design notes and key decisions are in [ARCHITECTURE.md](ARCHITECTURE.md).
Contribution guidelines are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Security & disclaimer

Please read [SECURITY.md](SECURITY.md). In short: the session file is account-level
access, all secrets stay in a git-ignored `.env`, and message text is sent to a
third-party AI provider for summarization. Automating a **user account** can violate
Telegram's Terms of Service — **use at your own risk**, keep usage personal.

## License

[MIT](LICENSE) © Maksat Guwançmyradow
