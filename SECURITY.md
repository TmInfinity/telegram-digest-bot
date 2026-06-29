# Security

This project is a **self-hosted personal tool**. You run your own instance with
your own credentials — there is no shared server and no third party ever receives
your Telegram session.

## The session file is account-level access

On first login, Telethon creates `ozet_session.session`. **This file grants full
access to your Telegram account** — anyone who has it can read and send messages as
you, without your phone or password.

- **Never** commit it, share it, upload it, or include it in a backup that others can read.
- It is already listed in `.gitignore` (`*.session`). Keep it that way.
- If you think it leaked, immediately terminate the session: Telegram app →
  Settings → Devices → Active sessions → end the session, then delete the file and
  log in again.

## Secrets

All secrets live in `.env` (git-ignored): Telegram API credentials, bot token, and
your OpenRouter API key. Use `.env.example` as a template. Recommended: `chmod 600 .env`.

The app never logs secrets. Logs (`app.log`) contain only operational info and are
git-ignored.

## Data flow / privacy

- Messages are read locally by your userbot and sent to **OpenRouter** for
  summarization. Treat that as sending the text to a third-party AI provider.
- Free (`:free`) models on OpenRouter may log prompts for training. If your group
  content is sensitive, use a paid model with a stricter data policy and review
  OpenRouter's privacy settings.

## Telegram Terms of Service

This tool automates a **user account** (a "userbot"), not just a bot account.
Automating a user account can violate Telegram's Terms of Service and may, in rare
cases, lead to limits or a ban. **Use at your own risk.** Keep usage personal and
reasonable (this tool only reads your own unread messages and summarizes them).

## Reporting a vulnerability

If you find a security issue, please open a GitHub issue describing it (without
including any secrets), or contact the maintainer privately.
