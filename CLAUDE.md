# CLAUDE.md

Context for AI coding agents (Claude Code, etc.) working in this repo.

- **What it is / how it works:** see [ARCHITECTURE.md](ARCHITECTURE.md).
- **Usage & setup:** see [README.md](README.md).
- **Security rules:** see [SECURITY.md](SECURITY.md).

## Dev workflow

- Managed with `uv`. Run: `uv run python bot.py`.
- Syntax check: `python3 -m py_compile bot.py i18n.py`.
- Lint (CI enforces this): `uvx ruff check .`.
- Add a dependency: `uv add <pkg>`.

## Conventions to follow

- **Never hardcode user-facing text in `bot.py`.** Add it to `i18n.py` as a key in
  **all** languages (`en`, `tr`, `ru`, `tk`); CI checks key parity. Resolve with `t("key")`.
- **Build buttons/labels via `t()` at call time**, not as module constants, or they
  won't re-translate when the language changes.
- New AI prompts are English templates with a `{dil}` output-language placeholder; the
  empty-output sentinel is the constant `__EMPTY__`.
- In Telethon topic loops use `tp` as the loop variable, not `t` (it would shadow the
  translation function).
- **Never log or commit secrets** (`.env`, `*.session`, tokens). They are git-ignored.
- Telegram messages use HTML parse mode — escape dynamic text with `html.escape()`.

## Commands

`/ozet`, `/otomatik`, `/dil`, `/durum`, `/start`, and a hidden `/test_bulten` that runs
the digest immediately.

## Running in the background (macOS)

A `launchd` template is provided at `deploy/com.telegram-digest.plist.example`. After a
code change, reload the service:

```
launchctl bootout   gui/$(id -u)/com.telegram-digest
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.telegram-digest.plist
```

Don't run a second instance (e.g. `uv run python bot.py`) while the launchd copy is
active — the bot token would conflict.
