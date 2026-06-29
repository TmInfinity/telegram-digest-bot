#!/usr/bin/env python3
"""
Chat ID bulucu — bir kerelik yardımcı script.

Botuna Telegram'da /start (ya da herhangi bir mesaj) gönderdikten sonra
bunu çalıştır. Botun aldığı son mesajlara bakıp senin chat ID'ini bulur.

Kullanım:
    uv run python chatid_bul.py
"""

import os
import sys
import urllib.request
import json

TOKEN = os.environ.get("TG_BOT_TOKEN", "")

if not TOKEN:
    print("HATA: TG_BOT_TOKEN ortam değişkeni ayarlı değil.")
    sys.exit(1)

url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

try:
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.load(resp)
except Exception as e:
    print(f"İstek başarısız: {e}")
    sys.exit(1)

if not data.get("ok"):
    print(f"Telegram hata döndü: {data}")
    sys.exit(1)

updates = data.get("result", [])
if not updates:
    print("Bot henüz hiç mesaj almamış görünüyor.")
    print("Telegram'da botuna gidip /start (ya da herhangi bir mesaj) gönder,")
    print("sonra bu script'i tekrar çalıştır.")
    sys.exit(0)

# Mesaj gönderen benzersiz kişileri topla
kisiler = {}
for u in updates:
    msg = u.get("message") or u.get("edited_message")
    if not msg:
        continue
    chat = msg.get("chat", {})
    cid = chat.get("id")
    ad = chat.get("first_name", "") or chat.get("title", "")
    if cid is not None:
        kisiler[cid] = ad

print("\nBotunla konuşan kişiler / chat ID'leri:\n")
for cid, ad in kisiler.items():
    print(f"  Chat ID: {cid}   ({ad})")

print("\n.zshrc'ye eklemen gereken satır (kendi ID'in ile):")
ilk_id = next(iter(kisiler))
print(f'\n  export TG_CHAT_ID="{ilk_id}"\n')
