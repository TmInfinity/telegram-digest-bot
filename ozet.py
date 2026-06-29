#!/usr/bin/env python3
"""
Telegram okunmamış mesaj özetleyici — Gemini sürümü.

Kullanım:
    python ozet.py                 -> okunmamış mesajı olan gruplari listeler, seçtirir
    python ozet.py "Grup Adi"      -> ada göre grubu bulur ve özetler

Gerekli ortam değişkenleri:
    TG_API_ID           my.telegram.org'dan
    TG_API_HASH         my.telegram.org'dan
    GEMINI_API_KEY      Google AI Studio'dan (aistudio.google.com/apikey)
    TG_BOT_TOKEN        BotFather'dan (özeti gönderecek bot)
    TG_CHAT_ID          özetin gönderileceğin senin chat ID'in
"""

import os
import sys
import urllib.request
import urllib.parse
import json

from dotenv import load_dotenv
load_dotenv()  # ayni klasordeki .env dosyasini okur

from telethon import TelegramClient
from google import genai

# ----------------------------- Ayarlar -----------------------------
API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TG_CHAT_ID", "")

SESSION = "ozet_session"          # .session dosyasinin adi (hesabinin tam erisimi — gizli tut!)
MODEL = "gemini-2.5-flash"        # ucuz/hizli ve ucretsiz katmana uygun. En yenisi: "gemini-3.5-flash"
MAX_MESSAGES = 500                # tek seferde cekilecek azami okunmamis mesaj (token guvenligi)
# -------------------------------------------------------------------

client = TelegramClient(SESSION, API_ID, API_HASH)


def gonderen_adi(msg):
    """Mesaji yazan kisinin adini dondurur, bulamazsa ID'sini."""
    s = msg.sender
    if s is None:
        return str(msg.sender_id)
    ad = (getattr(s, "first_name", None)
          or getattr(s, "title", None)
          or getattr(s, "username", None))
    return ad or str(msg.sender_id)


async def okunmamis_gruplari_getir():
    """Okunmamis mesaji olan gruplari (Dialog) bir liste olarak dondurur."""
    gruplar = []
    async for dialog in client.iter_dialogs():
        if dialog.is_group and dialog.unread_count > 0:
            gruplar.append(dialog)
    return gruplar


async def grup_bul(ad_parcasi):
    """Adinda verilen metni gecen (buyuk/kucuk harf duyarsiz) ilk grubu bulur."""
    hedef = ad_parcasi.lower()
    async for dialog in client.iter_dialogs():
        if dialog.is_group and hedef in dialog.name.lower():
            return dialog
    return None


async def okunmamis_mesajlar(dialog):
    """Verilen grubun okunmamis mesajlarini eskiden yeniye sirali dondurur."""
    son_okunan = dialog.dialog.read_inbox_max_id  # bu ID'den sonrakiler okunmamis
    mesajlar = []
    async for msg in client.iter_messages(
        dialog.entity, min_id=son_okunan, limit=MAX_MESSAGES
    ):
        if msg.text:  # sadece metinli mesajlar (foto/sticker vs. atlanir)
            mesajlar.append(msg)
    mesajlar.reverse()  # iter_messages yeniden eskiye verir; kronolojik yapariz
    return mesajlar


def ozetle(grup_adi, mesajlar):
    """Mesajlari Gemini'ye gonderip Turkce ozet alir."""
    konusma = "\n".join(f"{gonderen_adi(m)}: {m.text}" for m in mesajlar)

    prompt = f"""Aşağıda "{grup_adi}" adlı Telegram grubundaki okunmamış mesajlar var.
Bunları benim için özetle. Kurallar:
- Türkçe yaz.
- Konu konu, kısa ve net özetle.
- Bana yöneltilen bir soru, bir rica ya da yapmam gereken bir şey varsa ayrıca belirt.
- Önemli kararlar, tarihler veya bağlantılar varsa kaybolmasınlar.
- Gereksiz selamlaşma/dolgu mesajlarını atla.

Mesajlar:
{konusma}"""

    genai_client = genai.Client(api_key=GEMINI_API_KEY)
    resp = genai_client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )
    return resp.text


def bota_gonder(metin):
    """Ozeti BotFather botu araciligiyla senin DM'ine gonderir."""
    if not (BOT_TOKEN and CHAT_ID):
        print("(Bot token / chat ID ayarli degil, bota gonderilmedi.)")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    veri = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": metin,
    }).encode()
    try:
        with urllib.request.urlopen(url, data=veri, timeout=20) as r:
            sonuc = json.load(r)
        if sonuc.get("ok"):
            print("📨 Özet bota gönderildi.")
        else:
            print(f"Bota gönderilemedi: {sonuc}")
    except Exception as e:
        print(f"Bota gönderilemedi: {e}")


async def main():
    # Komut satirindan grup adi verildiyse onu kullan
    if len(sys.argv) > 1:
        ad = " ".join(sys.argv[1:])
        dialog = await grup_bul(ad)
        if dialog is None:
            print(f"'{ad}' ile eşleşen bir grup bulunamadı.")
            return
    else:
        # Verilmediyse okunmamis gruplari listele, seçtir
        gruplar = await okunmamis_gruplari_getir()
        if not gruplar:
            print("Okunmamış mesajı olan grup yok. 🎉")
            return
        print("\nOkunmamış mesajı olan gruplar:\n")
        for i, g in enumerate(gruplar, 1):
            print(f"  {i}. {g.name}  ({g.unread_count} okunmamış)")
        secim = input("\nHangi grup? (numara): ").strip()
        if not secim.isdigit() or not (1 <= int(secim) <= len(gruplar)):
            print("Geçersiz seçim.")
            return
        dialog = gruplar[int(secim) - 1]

    print(f"\n'{dialog.name}' grubunun okunmamış mesajları çekiliyor...")
    mesajlar = await okunmamis_mesajlar(dialog)
    if not mesajlar:
        print("Metinli okunmamış mesaj bulunamadı.")
        return

    print(f"{len(mesajlar)} mesaj bulundu, özetleniyor...\n")
    ozet = ozetle(dialog.name, mesajlar)

    print("=" * 60)
    print(f"ÖZET — {dialog.name}")
    print("=" * 60)
    print(ozet)
    print("=" * 60)

    # Özeti bota (kendi DM'ine) gönder
    bota_gonder(f"📋 ÖZET — {dialog.name}\n\n{ozet}")

    # Özet bittikten sonra: okundu işaretlemek ister mi diye sor
    cevap = input(
        f"\nBu gruptaki ({dialog.unread_count}) okunmamış mesajı okundu yapayım mı? [e/H]: "
    ).strip().lower()
    if cevap in ("e", "evet", "y", "yes"):
        await client.send_read_acknowledge(dialog.entity)
        print("✅ Okundu olarak işaretlendi.")
    else:
        print("Dokunulmadı, okunmamış olarak kaldı.")


if __name__ == "__main__":
    if not (API_ID and API_HASH):
        print("HATA: TG_API_ID ve TG_API_HASH ortam değişkenleri ayarlı değil.")
        sys.exit(1)
    if not GEMINI_API_KEY:
        print("HATA: GEMINI_API_KEY ortam değişkeni ayarlı değil.")
        sys.exit(1)

    # `with client` ilk calistirmada telefon + kod ile giris yaptirir, .session dosyasi olusturur
    with client:
        client.loop.run_until_complete(main())
