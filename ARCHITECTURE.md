# Architecture

Design notes and key decisions behind Telegram Digest Bot. For usage and setup, see
the [README](README.md).

## Overview

A self-hosted, single-user Telegram message summarizer. The owner is whoever installs
it. It has two main capabilities:

1. **On-demand summary** (`/ozet`) — lists groups/forum topics with unread messages,
   summarizes the selected chat in one of three modes, or exports a Q&A file.
2. **Automatic daily digest** (`/otomatik` + every morning at 09:00) — summarizes the
   last 24h of selected groups/topics into an information-focused digest, delivers it,
   then marks those chats read.

## Dual-identity design

Telegram **bots cannot read group history** they aren't actively part of, so two
identities run inside the same asyncio event loop:

- **Telethon (userbot)** — the user's *own* account; it **reads** messages. `tele`
  (the `TelegramClient`) is a module global, awaited directly inside bot handlers.
- **python-telegram-bot** — a separate BotFather bot; it **talks** to the user
  (commands, inline buttons, delivery).

## Reading unread messages

- Telegram tracks `read_inbox_max_id`; messages with a higher id are unread. They are
  pulled with `iter_messages(min_id=read_inbox_max_id)`.
- **Forum groups** (`dialog.entity.forum == True`): the group-level `unread_count` is
  unreliable, so `okunmamis_gruplari_getir()` checks real unread **per topic** via
  `GetForumTopicsRequest`. Topic messages are fetched with
  `iter_messages(reply_to=topic_id, ...)`.
- `GetForumTopicsRequest` lives under `telethon.tl.functions.messages` (Telegram moved
  it out of `channels`) and takes `peer=` (not `channel=`).
- **Marking read:** `ReadDiscussionRequest(peer, msg_id=topic_id, read_max_id=top_message)`
  for a topic; `tele.send_read_acknowledge(entity)` for a normal group.

## Summarization (OpenRouter)

- Provider: **OpenRouter** (OpenAI-compatible HTTP API, called with `httpx`). The model
  is set via `OPENROUTER_MODEL` (default `deepseek/deepseek-chat-v3-0324` — cheap, good
  multilingual quality, no aggressive content filter). An earlier version used Google
  Gemini, but `gemini-2.5-flash` frequently blocked benign group messages with
  `PROHIBITED_CONTENT`, which motivated the switch.
- `_ai_cagir()` is the shared call with a 4-attempt backoff for 429/5xx/overload. It
  turns an empty response into an error instead of silently passing `None`. It is
  **synchronous and blocking**, so handlers call it via `asyncio.to_thread(_ai_cagir, …)`
  — otherwise the whole event loop (including Telethon) would freeze during a request.
- Three summary modes — `genel` (general), `bilgi` (knowledge & tips), `aksiyon`
  (actions & tasks) — defined in `MOD_PROMPTLARI`. When a mode finds nothing, the model
  returns a fixed `__EMPTY__` sentinel (`_bos_mu`) and the UI suggests other modes.
- The daily digest uses a separate `BULTEN_PROMPT` (information-focused, not a to-do
  list). It ends with a `KRITIK: <ids>` line marking the 1-2 most critical messages
  (`_kritik_ayikla`); those get a `t.me/c/...` deep-link button (`_msg_link`).

## Q&A export

- `/ozet` → pick group/topic → "Q&A file" button.
- Finds the group **owner** (creator) via `grup_sahibi_bul` (`ChannelParticipantCreator`).
- Pairs the owner's unread messages with the questions they replied to (`_yanit_hedefi`).
- Each export gets its own folder: `soru_cevap/<group>_<timestamp>/` with a `.md` plus an
  `resimler/` (images) directory. Images are downloaded and embedded as
  `![](resimler/x.jpg)`; the `.md` is delivered to Telegram as a document while the
  images stay viewable in the local folder.

## Formatting

- **Messages are sent with HTML parse mode.** Dynamic text is always escaped with
  `html.escape()` (raw Markdown previously caused parse errors). Model output uses only
  `**bold**`, converted safely to `<b>` by `_bicim()` (escape first, then convert — so
  model-supplied `<`/`>`/`&` cannot inject markup).
- Long summaries are wrapped in `<blockquote expandable>` so the message stays compact
  and expands on tap. Anything above Telegram's 4096-char limit is split by `_parcala()`.
- `msg.text` in Telethon already includes image captions.

## Internationalization (i18n)

- All user-facing strings live in `i18n.py` as `STRINGS[lang][key]`. Languages: `en`
  (default), `tr`, `ru`, `tk`. `i18n.t("key", **kw)` resolves a string; a missing key
  falls back to English. The current language is a module global (`i18n.set_dil`), which
  is sufficient for a single-user tool.
- **Button/command labels are produced by `t()` at call time** (not module constants),
  so they re-translate when the language changes — hence the `kapat_btn()` / `geri_btn()`
  helpers.
- AI prompts are English templates; the output language is injected via `{dil}`
  (`i18n.PROMPT_LANG`). The empty-output sentinel is the language-independent constant
  `__EMPTY__`.
- The language is loaded from `ayarlar.json` at startup and changed with `/dil`.
- Note: in Telethon topic loops, a loop variable named `t` would shadow the translation
  function `t`. Block `for t in …:` loops use `tp` instead (comprehensions don't leak).

## Configuration & persistence

- `.env` (git-ignored; see `.env.example`): `TG_API_ID`, `TG_API_HASH`,
  `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (optional), `TG_BOT_TOKEN`, `TG_CHAT_ID`.
- `ayarlar.json`: `{otomatik_acik, gruplar, konular, son_bulten, son_bulten_tarih,
  son_mod, dil}`. `son_bulten_tarih` (YYYY-MM-DD) guarantees one digest per day and
  drives sleep catch-up; `son_mod` is the remembered last mode; `dil` is the language.
- `ozet_session.session`: the Telethon session — **full account access; never share or
  commit it.** See [SECURITY.md](SECURITY.md).
- Logs: `app.log` (rotating, timestamped, 1 MB × 3 backups).

## Automatic digest & sleep catch-up

- A daily job runs at 09:00 (local timezone). Because launchd only runs while the
  machine is awake, a missed 09:00 trigger (laptop asleep) is recovered by
  `bulten_telafi_job`, which checks every 120 s and runs today's digest as soon as the
  machine wakes after 09:00. `son_bulten_tarih` + an asyncio lock guarantee exactly one
  digest per day and prevent the scheduled and catch-up jobs from racing.

## Security model

Every command and button checks the owner (`sadece_sahip()` / `SAHIP_ID`); requests from
anyone else are ignored. Secrets live only in a git-ignored `.env`. Summarized message
text is sent to a third-party AI provider (OpenRouter). See [SECURITY.md](SECURITY.md).

## Known limits

- `MAX_MESSAGES = 500`: in very busy groups the oldest unread messages can be dropped.
- The digest only runs while the host is on; if the machine never wakes during a day,
  that day's digest is skipped.
- No image analysis — a deliberate quota/speed decision; images are only embedded raw in
  the Q&A export.
- The mode-selection cache (`ONBELLEK`) is in-memory, so pending sessions are lost on
  restart (the user is told to start again with `/ozet`).
