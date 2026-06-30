# Contributing

Thanks for your interest! This is a self-hosted personal tool, but contributions are welcome.

## Development

```bash
uv sync
uv run python -m py_compile bot.py i18n.py    # syntax check
uvx ruff check .                              # lint (CI runs this)
```

Run your own instance with your own `.env` (see [`.env.example`](.env.example)) to test changes.

## Guidelines

- Keep user-facing strings in [`i18n.py`](i18n.py) — never hardcode text in `bot.py`.
  Add the key to **all** languages (`en`, `tr`, `ru`, `tk`); CI checks key parity.
- New AI prompts go in English with a `{dil}` output-language placeholder.
- Never commit secrets (`.env`, `*.session`, `ayarlar.json`). See [SECURITY.md](SECURITY.md).
- Match the existing style; `ruff check .` must pass.

## Translations

Improvements to the `ru` and `tk` translations in `i18n.py` are especially welcome —
open a PR editing the relevant language block.
