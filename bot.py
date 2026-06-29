#!/usr/bin/env python3
"""
İnteraktif Telegram özet botu — forum destekli, şık arayüzlü, çok modlu.

Akış: /ozet → grup seç → (forumsa konu seç) → MOD seç → özet.
Modlar: 📝 Genel · 💡 Bilgi & ipucu · 🎯 Aksiyon & görevler
Her özetin altında diğer modlarda tekrar deneme butonları vardır.

Gerekli ortam değişkenleri (.env):
    TG_API_ID, TG_API_HASH, GEMINI_API_KEY, TG_BOT_TOKEN, TG_CHAT_ID
"""

import os
import sys
import time
import html
import uuid
import json
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone, time as saat

from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from telethon.tl.functions.messages import GetForumTopicsRequest, ReadDiscussionRequest
from telethon.tl.types import (
    ChannelParticipantsAdmins, ChannelParticipantCreator, ChatParticipantCreator,
)
from google import genai

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

# ----------------------------- Loglama -----------------------------
# Tarih damgalı, kendini temizleyen log: 1MB'ı geçince döner, en fazla 3 yedek (~4MB)
_LOG_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")
_log_handler = RotatingFileHandler(
    _LOG_DOSYA, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
))
logging.basicConfig(level=logging.INFO, handlers=[_log_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
log = logging.getLogger("ozetbot")

BASLANGIC = datetime.now()  # bot ne zaman başladı (çalışma süresi için)
# -------------------------------------------------------------------

# ----------------------------- Ayarlar -----------------------------
API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
SAHIP_ID = int(os.environ.get("TG_CHAT_ID", "0"))

SESSION = "ozet_session"
MODEL = "gemini-2.5-flash"
MAX_MESSAGES = 500
# -------------------------------------------------------------------

tele = TelegramClient(SESSION, API_ID, API_HASH)

# Mod tanımları: anahtar -> (emoji, ad)
MODLAR = {
    "genel":   ("📝", "Genel özet"),
    "bilgi":   ("💡", "Bilgi & ipucu"),
    "aksiyon": ("🎯", "Aksiyon & görevler"),
}

# Her mod için Gemini prompt şablonu ({baslik} ve {konusma} ile)
MOD_PROMPTLARI = {
    "genel": """Aşağıda "{baslik}" adlı Telegram sohbetindeki okunmamış mesajlar var.
Genel bir özet çıkar:
- Türkçe yaz, konu konu, kısa ve net.
- Ne konuşulmuş, kim ne demiş.
- Bana yöneltilen soru/rica/yapılacak iş varsa ayrıca belirt.
- Önemli karar, tarih veya bağlantı kaybolmasın.
- Selamlaşma/dolgu mesajlarını atla.
- Markdown işareti (*, #, _, `) KULLANMA. Madde için "•" kullan.

Mesajlar:
{konusma}""",

    "bilgi": """Aşağıda "{baslik}" adlı Telegram sohbetindeki okunmamış mesajlar var.
Görevin: SADECE faydalı/öğretici içeriği çıkarmak — bilgiler, ipuçları, taktikler,
kaynaklar, linkler, öneriler, nasıl-yapılır türü bilgiler.
- Sohbet/laf kalabalığı/selamlaşma/şaka kısmını TAMAMEN atla.
- Faydalı şeyleri madde madde "•", net ve uygulanabilir yaz.
- Link/kaynak varsa aynen koru.
- Türkçe yaz. Markdown işareti (*, #, _, `) KULLANMA.
- EĞER bu sohbette kayda değer hiçbir faydalı bilgi/ipucu yoksa, başka hiçbir şey
  yazmadan SADECE şu tek kelimeyi yaz: BOŞ

Mesajlar:
{konusma}""",

    "aksiyon": """Aşağıda "{baslik}" adlı Telegram sohbetindeki okunmamış mesajlar var.
Görevin: SADECE bana/bize düşen aksiyonları çıkarmak — yapılacak işler, son tarihler,
randevular, formlar, başvurular, hatırlanması gereken şeyler, cevap bekleyen sorular.
- Her birini madde madde "•" yaz; varsa tarih/saat/son başvuru gününü belirt.
- Genel sohbeti, bilgi paylaşımını ve dolguyu atla.
- Türkçe yaz. Markdown işareti (*, #, _, `) KULLANMA.
- EĞER kayda değer hiçbir aksiyon/görev/tarih yoksa, başka hiçbir şey yazmadan
  SADECE şu tek kelimeyi yaz: BOŞ

Mesajlar:
{konusma}""",
}

# Otomatik günlük bülten prompt'u (bilgi odaklı, detaylı + kritik mesaj ID'leri)
BULTEN_PROMPT = """Aşağıda "{baslik}" grubunun SON 24 SAATTEKİ mesajları var.
Her mesajın başında [ID:sayı] etiketi var.

Bana DETAYLI ve BİLGİ ODAKLI bir bülten hazırla. Amaç: bu grupta paylaşılan
önemli/öğretici bilgileri KAÇIRMADAN toplamak.

📰 BÜLTEN
- Sohbette geçen faydalı/öğretici her bilgiyi topla: taktikler, ipuçları,
  nasıl-yapılır bilgileri, stratejiler, kaynaklar, linkler, öneriler, dikkat
  çekici veriler, deneyimler, açıklamalar.
- Konu konu, derli toplu, madde madde "•" yaz.
- Uzun olması sorun değil; önemli hiçbir bilgi atlanmasın. Ama gereksiz sohbeti,
  şakaları, selamlaşmayı, dolguyu atla.
- Bir konu üzerine birden çok kişi konuştuysa, bilgiyi birleştirip net yaz.

🔔 SANA ÖZEL (varsa)
- Eğer sana DOĞRUDAN yöneltilmiş bir soru, rica veya seni ilgilendiren önemli
  bir duyuru varsa, bunu en altta kısaca belirt. Yoksa bu bölümü hiç yazma.

Kurallar:
- Türkçe yaz. Markdown işareti (*, #, _, `) KULLANMA.
- [ID:..] etiketlerini metne YAZMA.
- En sonda, AYRI bir satırda, en kritik 1-2 mesajın ID'sini şu formatta ver:
  KRITIK: 12345, 12389
  Kritik mesaj yoksa: KRITIK: yok

Mesajlar:
{konusma}"""

# Çekilen mesajları kısa süreli tutan önbellek (mod değiştirmede yeniden çekmemek için)
ONBELLEK = {}

# Otomatik özet ayarları (kalıcı dosya)
AYAR_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ayarlar.json")


def ayarlari_oku():
    """ayarlar.json'u okur; yoksa varsayılan döndürür."""
    if os.path.exists(AYAR_DOSYA):
        try:
            with open(AYAR_DOSYA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"otomatik_acik": False, "gruplar": [], "konular": []}  # gruplar: id, konular: [grup_id, konu_id]


def ayarlari_yaz(ayar):
    try:
        with open(AYAR_DOSYA, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error("Ayar yazılamadı: %s", e)


# ======================= Yardımcı fonksiyonlar =======================

def gonderen_adi(msg):
    s = msg.sender
    if s is None:
        return str(msg.sender_id)
    ad = (getattr(s, "first_name", None)
          or getattr(s, "title", None)
          or getattr(s, "username", None))
    return ad or str(msg.sender_id)


def is_forum(dialog):
    return bool(getattr(dialog.entity, "forum", False))


async def topiclari_getir(entity):
    result = await tele(GetForumTopicsRequest(
        peer=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100
    ))
    return [t for t in result.topics if getattr(t, "title", None) is not None]


async def okunmamis_gruplari_getir():
    sonuc = []
    async for dialog in tele.iter_dialogs():
        if not dialog.is_group:
            continue
        if is_forum(dialog):
            try:
                topicler = await topiclari_getir(dialog.entity)
            except Exception:
                continue
            okunmamis_konular = [t for t in topicler if getattr(t, "unread_count", 0) > 0]
            if okunmamis_konular:
                toplam = sum(t.unread_count for t in okunmamis_konular)
                sonuc.append((dialog, toplam))
        else:
            if dialog.unread_count > 0:
                sonuc.append((dialog, dialog.unread_count))
    return sonuc


async def grup_dialog_bul(grup_id):
    async for dialog in tele.iter_dialogs():
        if dialog.id == grup_id:
            return dialog
    return None


async def okunmamis_mesajlar(dialog):
    son_okunan = dialog.dialog.read_inbox_max_id
    mesajlar = []
    async for msg in tele.iter_messages(dialog.entity, min_id=son_okunan, limit=MAX_MESSAGES):
        if msg.text:
            mesajlar.append(msg)
    mesajlar.reverse()
    return mesajlar


async def topic_unread_mesajlar(entity, topic):
    mesajlar = []
    async for msg in tele.iter_messages(
        entity, reply_to=topic.id, min_id=topic.read_inbox_max_id, limit=MAX_MESSAGES
    ):
        if msg.text:
            mesajlar.append(msg)
    mesajlar.reverse()
    return mesajlar


async def son24_mesajlar(entity, topic_id=None):
    """Son 24 saatte yazılan metinli mesajları (kronolojik) döndürür."""
    sinir = datetime.now(timezone.utc) - timedelta(hours=24)
    mesajlar = []
    kwargs = {"limit": MAX_MESSAGES}
    if topic_id is not None:
        kwargs["reply_to"] = topic_id
    async for msg in tele.iter_messages(entity, **kwargs):
        if msg.date < sinir:
            break
        if msg.text:
            mesajlar.append(msg)
    mesajlar.reverse()
    return mesajlar


def _msg_link(chat_id, msg_id, topic_id=None):
    """Bir mesaja Telegram derin bağlantısı üretir (t.me/c/...)."""
    cid = str(chat_id)
    cid = cid[4:] if cid.startswith("-100") else cid.lstrip("-")
    if topic_id and topic_id != 1:
        return f"https://t.me/c/{cid}/{topic_id}/{msg_id}"
    return f"https://t.me/c/{cid}/{msg_id}"


def _kritik_ayikla(metin):
    """Gemini çıktısından 'KRITIK: ...' satırını ayıklar; (gövde, [id'ler]) döndürür."""
    govde_satirlar, kritik_ids = [], []
    for s in (metin or "").splitlines():
        if s.strip().upper().startswith("KRITIK"):
            kisim = s.split(":", 1)[1] if ":" in s else ""
            for parca in kisim.replace(",", " ").split():
                if parca.isdigit():
                    kritik_ids.append(int(parca))
        else:
            govde_satirlar.append(s)
    return "\n".join(govde_satirlar).strip(), kritik_ids[:2]


# ---------------- Soru-Cevap çıkarımı ----------------

async def grup_sahibi_bul(entity):
    """Grubun kurucusunun (owner) kullanıcı id'sini döndürür; bulamazsa None."""
    # Kanal/süpergrup: admin listesinde kurucuyu ara
    try:
        adminler = await tele.get_participants(entity, filter=ChannelParticipantsAdmins())
        for u in adminler:
            if isinstance(getattr(u, "participant", None), ChannelParticipantCreator):
                return u.id
    except Exception:
        pass
    # Temel grup: tüm katılımcılarda kurucuyu ara
    try:
        for u in await tele.get_participants(entity):
            if isinstance(getattr(u, "participant", None), ChatParticipantCreator):
                return u.id
    except Exception:
        pass
    return None


def _yanit_hedefi(msg, topic_id):
    """Mesaj gerçekten bir mesaja yanıtsa o mesajın id'sini, değilse None döndürür."""
    rt = msg.reply_to
    if rt is None:
        return None
    hedef = getattr(rt, "reply_to_msg_id", None)
    if hedef is None:
        return None
    if topic_id is not None:
        # Forum: reply_to_top_id yoksa ya da hedef topic kökü ise gerçek yanıt değil
        top = getattr(rt, "reply_to_top_id", None)
        if top is None or hedef == topic_id:
            return None
    return hedef


def _resim_var_mi(msg):
    """Mesajda gömülebilir bir resim var mı?"""
    if getattr(msg, "photo", None):
        return True
    doc = getattr(msg, "document", None)
    if doc is not None:
        mime = getattr(doc, "mime_type", "") or ""
        if mime.startswith("image/"):
            return True
    return False


async def _resimleri_indir(mesajlar, resim_kls):
    """Verilen mesajlardaki resimleri indirir; {msg_id: [göreli_yol,...]} döndürür."""
    harita = {}
    for m in mesajlar:
        if m is not None and _resim_var_mi(m):
            try:
                yol = await m.download_media(file=os.path.join(resim_kls, str(m.id)))
                if yol:
                    rel = os.path.join("resimler", os.path.basename(yol))
                    harita.setdefault(m.id, []).append(rel)
            except Exception as e:
                log.error("resim indirme hata: %s", e)
    return harita


async def _sahip_okunmamis_mesajlar(dialog, topic_id, owner_id):
    """Grup sahibinin okunmamış (metinli veya resimli) mesajlarını kronolojik döndürür."""
    if topic_id is None:
        son = dialog.dialog.read_inbox_max_id
        it = tele.iter_messages(dialog.entity, min_id=son, limit=MAX_MESSAGES)
    else:
        topicler = await topiclari_getir(dialog.entity)
        topic = next((t for t in topicler if t.id == topic_id), None)
        son = topic.read_inbox_max_id if topic else 0
        it = tele.iter_messages(dialog.entity, reply_to=topic_id, min_id=son, limit=MAX_MESSAGES)
    msgs = []
    async for m in it:
        if m.sender_id == owner_id and (m.text or _resim_var_mi(m)):
            msgs.append(m)
    msgs.reverse()
    return msgs


def _mesaj_blogu(satir, msg, resim_haritasi):
    """Bir mesajın metnini ve (varsa) resimlerini satır listesine ekler."""
    txt = (msg.text or "").strip()
    if txt:
        satir.append(txt)
    for rel in resim_haritasi.get(msg.id, []):
        satir.append(f"![]({rel})")
    if not txt and msg.id not in resim_haritasi:
        satir.append("(içerik yok)")


def _soru_cevap_md(baslik, sahip_mesajlari, sorular, topic_id, resim_haritasi):
    """Soru-cevap çiftlerinden (resimler gömülü) Markdown metni üretir."""
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    satir = [f"# Soru-Cevap — {baslik}", f"_{tarih} · {len(sahip_mesajlari)} cevap_", ""]
    yanitsiz = []
    cift_sayisi = 0
    for m in sahip_mesajlari:
        h = _yanit_hedefi(m, topic_id)
        if h and h in sorular and sorular[h] is not None:
            q = sorular[h]
            cift_sayisi += 1
            satir.append(f"### ❓ {gonderen_adi(q)}")
            _mesaj_blogu(satir, q, resim_haritasi)
            satir.append("")
            satir.append("**💬 Cevap:**")
            _mesaj_blogu(satir, m, resim_haritasi)
            satir.append("")
            satir.append("---")
            satir.append("")
        else:
            yanitsiz.append(m)
    if yanitsiz:
        satir.append("## Yanıt olmayan mesajlar")
        satir.append("")
        for m in yanitsiz:
            _mesaj_blogu(satir, m, resim_haritasi)
            satir.append("")
    return "\n".join(satir), cift_sayisi


def _konusma_metni(mesajlar):
    return "\n".join(f"{gonderen_adi(m)}: {m.text}" for m in mesajlar)


def _gemini_cagir(prompt):
    """Gemini'ye prompt gönderir; 503 gibi geçici hatalarda yeniden dener."""
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
    son_hata = None
    for deneme in range(4):
        try:
            resp = genai_client.models.generate_content(model=MODEL, contents=prompt)
            return resp.text
        except Exception as e:
            son_hata = e
            if deneme < 3:
                time.sleep(3 * (deneme + 1))
    raise son_hata


def ozetle(baslik, konusma, mod):
    prompt = MOD_PROMPTLARI[mod].format(baslik=baslik, konusma=konusma)
    return _gemini_cagir(prompt)


def _bos_mu(metin):
    t = (metin or "").strip()
    return len(t) <= 12 and "BOŞ" in t.upper()


def sadece_sahip(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == SAHIP_ID


def _parcala(metin, limit):
    parcalar = []
    while len(metin) > limit:
        kesme = metin.rfind("\n", 0, limit)
        if kesme <= 0:
            kesme = limit
        parcalar.append(metin[:kesme])
        metin = metin[kesme:].lstrip("\n")
    if metin:
        parcalar.append(metin)
    return parcalar


def _onbellek_ekle(veri):
    key = uuid.uuid4().hex[:10]
    ONBELLEK[key] = veri
    if len(ONBELLEK) > 60:  # şişmesin: eski yarıyı at
        for k in list(ONBELLEK.keys())[:30]:
            ONBELLEK.pop(k, None)
    return key


# ======================= Arayüz (UI) yardımcıları =======================

KAPAT_BTN = InlineKeyboardButton("❌ Kapat", callback_data="kapat")


async def _grup_listesi_kb():
    gruplar = await okunmamis_gruplari_getir()
    if not gruplar:
        return None, None
    butonlar = []
    for g, sayi in gruplar:
        isaret = "🗂" if is_forum(g) else "💬"
        butonlar.append([InlineKeyboardButton(
            f"{isaret} {g.name}  ·  {sayi}", callback_data=f"grp:{g.id}"
        )])
    butonlar.append([KAPAT_BTN])
    text = ("📋 <b>Okunmamış Gruplar</b>\n"
            "<i>Hangisini özetleyeyim?</i>\n"
            "<i>🗂 konulu grup · 💬 normal grup</i>")
    return text, InlineKeyboardMarkup(butonlar)


def _mod_secim_kb(key):
    """Özet öncesi: 3 mod butonu + Soru-Cevap + Geri/Kapat."""
    butonlar = [
        [InlineKeyboardButton(f"{MODLAR[m][0]} {MODLAR[m][1]}", callback_data=f"mod:{key}:{m}")]
        for m in MODLAR
    ]
    butonlar.append([InlineKeyboardButton(
        "📄 Soru-Cevap dosyası", callback_data=f"mod:{key}:sorucevap"
    )])
    butonlar.append([InlineKeyboardButton("⬅️ Geri", callback_data="geri"), KAPAT_BTN])
    return InlineKeyboardMarkup(butonlar)


def _diger_modlar_kb(key, aktif_mod, okundu_callback, bos):
    """Özet sonrası: okundu/kapat + diğer modlarda tekrar deneme butonları."""
    satirlar = []
    if not bos:
        satirlar.append([
            InlineKeyboardButton("✅ Okundu yap", callback_data=okundu_callback),
            KAPAT_BTN,
        ])
    digerler = [m for m in MODLAR if m != aktif_mod]
    satirlar.append([
        InlineKeyboardButton(f"🔄 {MODLAR[m][1]}", callback_data=f"mod:{key}:{m}")
        for m in digerler
    ])
    if bos:
        satirlar.append([InlineKeyboardButton("⬅️ Geri", callback_data="geri"), KAPAT_BTN])
    return InlineKeyboardMarkup(satirlar)


async def _mod_secimi_goster(query, baslik, mesajlar, okundu_callback, toplam,
                             grup_id=None, topic_id=None):
    """Mesajları önbelleğe alıp mod seçim butonlarını gösterir."""
    if not mesajlar:
        await query.edit_message_text("ℹ️ Metinli okunmamış mesaj bulunamadı.")
        return
    key = _onbellek_ekle({
        "baslik": baslik,
        "konusma": _konusma_metni(mesajlar),
        "sayi": len(mesajlar),
        "okundu": okundu_callback,
        "toplam": toplam,
        "grup_id": grup_id,
        "topic_id": topic_id,
    })
    await query.edit_message_text(
        f"📋 <b>{html.escape(baslik)}</b>\n<i>Ne yapayım?</i>",
        reply_markup=_mod_secim_kb(key), parse_mode="HTML",
    )


async def _ozeti_uret_goster(query, key, mod):
    """Önbellekten alıp seçilen modda özetler ve gösterir."""
    veri = ONBELLEK.get(key)
    if veri is None:
        await query.edit_message_text(
            "⌛ Bu özet oturumu artık geçerli değil. /ozet ile tekrar başla."
        )
        return

    emoji, ad = MODLAR[mod]
    await query.edit_message_text(f"🤖 Gemini özetliyor… ({emoji} {ad})")
    try:
        ozet = ozetle(veri["baslik"], veri["konusma"], mod)
    except Exception as e:
        msg = str(e)
        if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg:
            await query.edit_message_text("⚠️ Gemini şu an yoğun. Biraz sonra tekrar dene.")
        else:
            await query.edit_message_text(f"⚠️ Özetlenemedi: {html.escape(msg[:300])}")
        return

    baslik_g = html.escape(veri["baslik"])

    # Boş çıktı: diğer modları öner
    if _bos_mu(ozet):
        kb = _diger_modlar_kb(key, mod, veri["okundu"], bos=True)
        await query.edit_message_text(
            f"📋 <b>{baslik_g}</b>\n\n"
            f"ℹ️ <i>Bu modda ({emoji} {ad}) kayda değer bir şey çıkmadı.</i>\n"
            "Başka bir modda denemek ister misin?",
            reply_markup=kb, parse_mode="HTML",
        )
        return

    if veri["toplam"] is not None:
        sayac = (f"\n\n━━━━━━━━━\n"
                 f"📊 {veri['sayi']} metin mesajı · {emoji} {ad} · "
                 f"toplam {veri['toplam']} okunmamış")
    else:
        sayac = f"\n\n━━━━━━━━━\n📊 {veri['sayi']} metin mesajı · {emoji} {ad}"

    kb = _diger_modlar_kb(key, mod, veri["okundu"], bos=False)
    tam = f"📋 <b>{baslik_g}</b>\n\n{html.escape(ozet)}{sayac}"
    LIMIT = 3900

    if len(tam) <= LIMIT:
        await query.edit_message_text(tam, reply_markup=kb, parse_mode="HTML")
        return

    parcalar = _parcala(tam, LIMIT)
    for i, parca in enumerate(parcalar):
        son = (i == len(parcalar) - 1)
        k = kb if son else None
        if i == 0:
            await query.edit_message_text(parca, reply_markup=k, parse_mode="HTML")
        else:
            await query.message.reply_text(parca, reply_markup=k, parse_mode="HTML")


async def _soru_cevap_dosyasi(query, context, key):
    """Grup sahibinin okunmamış cevaplarını soru-cevap dosyasına çıkarır."""
    veri = ONBELLEK.get(key)
    if veri is None:
        await query.edit_message_text("⌛ Bu oturum artık geçerli değil. /ozet ile tekrar başla.")
        return
    grup_id = veri.get("grup_id")
    topic_id = veri.get("topic_id")
    baslik = veri["baslik"]

    dialog = await grup_dialog_bul(grup_id)
    if dialog is None:
        await query.edit_message_text("Grup bulunamadı.")
        return

    await query.edit_message_text("🔎 Grup sahibi tespit ediliyor…")
    owner_id = await grup_sahibi_bul(dialog.entity)
    if owner_id is None:
        await query.edit_message_text(
            "⚠️ Grup sahibi (kurucu) tespit edilemedi. "
            "Bu grup için soru-cevap çıkarımı yapamıyorum."
        )
        return

    await query.edit_message_text("📥 Grup sahibinin mesajları taranıyor…")
    sahip_mesajlari = await _sahip_okunmamis_mesajlar(dialog, topic_id, owner_id)
    if not sahip_mesajlari:
        await query.edit_message_text("ℹ️ Grup sahibinin okunmamış mesajı yok.")
        return

    # Yanıt verilen soruları toplu çek
    hedef_ids = []
    for m in sahip_mesajlari:
        h = _yanit_hedefi(m, topic_id)
        if h:
            hedef_ids.append(h)
    sorular = {}
    if hedef_ids:
        try:
            getirilen = await tele.get_messages(dialog.entity, ids=hedef_ids)
            for q in getirilen:
                if q is not None:
                    sorular[q.id] = q
        except Exception as e:
            log.error("soru çekme hata: %s", e)

    # Her dışa aktarım için kendi klasörü (md + resimler birlikte dursun)
    zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
    guvenli = re.sub(r"[^\w\-]+", "_", baslik)[:50].strip("_") or "grup"
    kok = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soru_cevap")
    export_kls = os.path.join(kok, f"{guvenli}_{zaman}")
    resim_kls = os.path.join(export_kls, "resimler")
    os.makedirs(resim_kls, exist_ok=True)

    # Resimleri indir (hem cevaplar hem sorular)
    await query.edit_message_text("🖼 Resimler indiriliyor…")
    indir_listesi = list(sahip_mesajlari) + [q for q in sorular.values() if q is not None]
    resim_haritasi = await _resimleri_indir(indir_listesi, resim_kls)

    await query.edit_message_text("📝 Dosya hazırlanıyor…")
    md, cift = _soru_cevap_md(baslik, sahip_mesajlari, sorular, topic_id, resim_haritasi)

    dosya = os.path.join(export_kls, f"{guvenli}.md")
    with open(dosya, "w", encoding="utf-8") as f:
        f.write(md)

    # Telegram'dan belge olarak gönder (metin için; resimler Mac klasöründe)
    await query.edit_message_text("📤 Dosya gönderiliyor…")
    try:
        with open(dosya, "rb") as f:
            await context.bot.send_document(
                chat_id=SAHIP_ID, document=f, filename=os.path.basename(dosya),
                caption=f"📄 {baslik} — {cift} soru-cevap, {len(sahip_mesajlari)} mesaj",
            )
    except Exception as e:
        await query.edit_message_text(f"⚠️ Dosya gönderilemedi: {html.escape(str(e)[:200])}")
        return

    # Okundu yap
    try:
        if topic_id is None:
            await tele.send_read_acknowledge(dialog.entity)
        else:
            topicler = await topiclari_getir(dialog.entity)
            topic = next((t for t in topicler if t.id == topic_id), None)
            if topic:
                await tele(ReadDiscussionRequest(
                    peer=dialog.entity, msg_id=topic_id, read_max_id=topic.top_message
                ))
    except Exception as e:
        log.error("okundu hata (soru-cevap): %s", e)

    resim_sayisi = sum(len(v) for v in resim_haritasi.values())
    await query.edit_message_text(
        f"✅ <b>Soru-Cevap dosyası hazır</b>\n"
        f"📄 {cift} soru-cevap çifti · 🖼 {resim_sayisi} resim\n"
        f"<i>Resimleri görmek için Mac'te bu klasörü aç:</i>\n"
        f"<code>{html.escape(export_kls)}</code>",
        parse_mode="HTML",
    )


# ======================= Bot komutları =======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Özet Al", callback_data="menu:ozet")
    ]])
    await update.message.reply_text(
        "👋 <b>Mesaj Özetleyici</b>\n\n"
        "Okunmamış grup ve forum konularını senin için özetlerim.\n\n"
        "📋  <b>Özet Al</b> — okunmamış grupları listeler\n"
        "👆  Grup → (konu) → mod seç → özet\n"
        "✅  <b>Okundu yap</b> ile temizle\n\n"
        "Modlar: 📝 Genel · 💡 Bilgi & ipucu · 🎯 Aksiyon\n\n"
        "Alttaki butona ya da /ozet komutuna bas.",
        reply_markup=kb, parse_mode="HTML",
    )


async def ozet_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    bekle = await update.message.reply_text("🔎 Gruplar taranıyor…")
    text, kb = await _grup_listesi_kb()
    if text is None:
        await bekle.edit_text("✅ Okunmamış mesajı olan grup yok. 🎉")
        return
    await bekle.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ---------------- Otomatik özet (Parça 1: seçim + aç/kapa) ----------------

async def _otomatik_ekrani_kb():
    """Otomatik özet ana ekranı. Normal grup = tek dokunuş seçer;
    forum grubu = içine girilir (konular ayrı seçilir)."""
    ayar = ayarlari_oku()
    secili_gruplar = set(ayar.get("gruplar", []))
    secili_konular = [tuple(x) for x in ayar.get("konular", [])]
    acik = ayar.get("otomatik_acik", False)

    gruplar = []
    async for dialog in tele.iter_dialogs():
        if dialog.is_group:
            gruplar.append(dialog)

    butonlar = []
    for g in gruplar:
        if is_forum(g):
            # Bu grupta kaç konu seçili?
            sayi = sum(1 for (gid, tid) in secili_konular if gid == g.id)
            etiket = f"🗂 {g.name}  ▶︎"
            if sayi:
                etiket += f"  ({sayi} konu seçili)"
            butonlar.append([InlineKeyboardButton(etiket, callback_data=f"oto_grp:{g.id}")])
        else:
            isaret = "✅" if g.id in secili_gruplar else "⬜"
            butonlar.append([InlineKeyboardButton(
                f"{isaret} 💬 {g.name}", callback_data=f"oto_sec:{g.id}"
            )])

    durum_btn = InlineKeyboardButton(
        "🟢 Otomatik: AÇIK (kapat)" if acik else "🔴 Otomatik: KAPALI (aç)",
        callback_data="oto_durum",
    )
    butonlar.insert(0, [durum_btn])
    butonlar.append([KAPAT_BTN])

    durum_yazi = "🟢 açık" if acik else "🔴 kapalı"
    toplam_secili = len(secili_gruplar) + len(secili_konular)
    text = (f"⏰ <b>Otomatik Günlük Özet</b>\n"
            f"Durum: {durum_yazi} · Her sabah 09:00\n"
            f"Seçili: {len(secili_gruplar)} grup + {len(secili_konular)} konu\n\n"
            f"<i>💬 normal grup: dokun = seç · 🗂 forum: dokun = konulara gir</i>")
    return text, InlineKeyboardMarkup(butonlar)


async def _otomatik_konu_kb(grup_id):
    """Bir forum grubunun konu seçim ekranı."""
    ayar = ayarlari_oku()
    secili_konular = [tuple(x) for x in ayar.get("konular", [])]

    dialog = await grup_dialog_bul(grup_id)
    if dialog is None:
        return "Grup bulunamadı.", InlineKeyboardMarkup([[KAPAT_BTN]])

    topicler = await topiclari_getir(dialog.entity)
    butonlar = []
    for t in topicler:
        isaret = "✅" if (grup_id, t.id) in secili_konular else "⬜"
        butonlar.append([InlineKeyboardButton(
            f"{isaret} {t.title}", callback_data=f"oto_konu:{grup_id}:{t.id}"
        )])
    butonlar.append([
        InlineKeyboardButton("⬅️ Geri", callback_data="oto_geri"), KAPAT_BTN
    ])

    text = (f"🗂 <b>{html.escape(dialog.name)}</b>\n"
            f"<i>Otomatiğe almak istediğin konuları seç.</i>")
    return text, InlineKeyboardMarkup(butonlar)


async def otomatik_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    bekle = await update.message.reply_text("🔎 Gruplar taranıyor…")
    text, kb = await _otomatik_ekrani_kb()
    await bekle.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ---------------- Otomatik özet (Parça 2: günlük bülten) ----------------

async def _bulten_gonder(bot, baslik, mesajlar, chat_id, topic_id=None):
    """Bir grup/konu için bülten üretip gönderir. Başarılıysa True döndürür."""
    # Son 24 saatte mesaj yoksa kısa not
    if not mesajlar:
        await bot.send_message(
            SAHIP_ID,
            f"📰 <b>{html.escape(baslik)}</b>\n\nℹ️ Son 24 saatte mesaj yok.",
            parse_mode="HTML",
        )
        return False

    konusma = "\n".join(f"[ID:{m.id}] {gonderen_adi(m)}: {m.text}" for m in mesajlar)
    try:
        ham = _gemini_cagir(BULTEN_PROMPT.format(baslik=baslik, konusma=konusma))
    except Exception as e:
        await bot.send_message(
            SAHIP_ID,
            f"📰 <b>{html.escape(baslik)}</b>\n\n⚠️ Özetlenemedi: {html.escape(str(e)[:200])}",
            parse_mode="HTML",
        )
        return False

    govde, kritik_ids = _kritik_ayikla(ham)

    # Kritik mesaj butonları
    btn_satir = []
    for i, mid in enumerate(kritik_ids, 1):
        etiket = "🔗 Önemli mesaja git" if len(kritik_ids) == 1 else f"🔗 Önemli #{i}"
        btn_satir.append(InlineKeyboardButton(etiket, url=_msg_link(chat_id, mid, topic_id)))
    kb = InlineKeyboardMarkup([btn_satir]) if btn_satir else None

    metin = f"📰 <b>{html.escape(baslik)}</b>\n\n{html.escape(govde)}"
    LIMIT = 3900
    parcalar = _parcala(metin, LIMIT) if len(metin) > LIMIT else [metin]

    for i, parca in enumerate(parcalar):
        son = (i == len(parcalar) - 1)
        k = kb if son else None
        try:
            await bot.send_message(SAHIP_ID, parca, reply_markup=k, parse_mode="HTML")
        except Exception:
            # Buton/link sorun çıkarırsa butonsuz tekrar dene
            await bot.send_message(SAHIP_ID, parca, parse_mode="HTML")
    return True


async def _bulteni_calistir(bot, zorla=False):
    """Seçili tüm grup ve konular için bülten üretir, sonra okundu yapar."""
    ayar = ayarlari_oku()
    if not zorla and not ayar.get("otomatik_acik"):
        return

    gruplar = ayar.get("gruplar", [])
    konular = [tuple(x) for x in ayar.get("konular", [])]

    if zorla and not gruplar and not konular:
        await bot.send_message(
            SAHIP_ID,
            "ℹ️ Otomatik özet için hiç grup/konu seçili değil. /otomatik ile seç.",
        )
        return

    # Normal gruplar
    for gid in gruplar:
        dialog = await grup_dialog_bul(gid)
        if dialog is None:
            continue
        mesajlar = await son24_mesajlar(dialog.entity)
        basari = await _bulten_gonder(bot, dialog.name, mesajlar, dialog.id)
        if basari:
            try:
                await tele.send_read_acknowledge(dialog.entity)
            except Exception as e:
                log.error("okundu hata (grup): %s", e)

    # Forum konuları
    for (gid, tid) in konular:
        dialog = await grup_dialog_bul(gid)
        if dialog is None:
            continue
        topicler = await topiclari_getir(dialog.entity)
        topic = next((t for t in topicler if t.id == tid), None)
        if topic is None:
            continue
        baslik = f"{dialog.name} › {topic.title}"
        mesajlar = await son24_mesajlar(dialog.entity, topic_id=tid)
        basari = await _bulten_gonder(bot, baslik, mesajlar, dialog.id, topic_id=tid)
        if basari:
            try:
                await tele(ReadDiscussionRequest(
                    peer=dialog.entity, msg_id=tid, read_max_id=topic.top_message
                ))
            except Exception as e:
                log.error("okundu hata (konu): %s", e)

    # Son bülten zamanını kaydet
    ayar2 = ayarlari_oku()
    ayar2["son_bulten"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    ayarlari_yaz(ayar2)
    log.info("Bülten çalıştı: %d grup, %d konu (zorla=%s)", len(gruplar), len(konular), zorla)


async def gunluk_bulten_job(context: ContextTypes.DEFAULT_TYPE):
    """Her sabah 09:00'da çalışır."""
    await _bulteni_calistir(context.bot, zorla=False)


async def test_bulten_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    await update.message.reply_text("🧪 Test bülteni çalıştırılıyor… (biraz sürebilir)")
    await _bulteni_calistir(context.bot, zorla=True)
    await update.message.reply_text("✅ Test bülteni tamamlandı.")


def _sure_metni(delta):
    """timedelta'yı 'X gün Y saat Z dakika' gibi okunur metne çevirir."""
    saniye = int(delta.total_seconds())
    gun, kalan = divmod(saniye, 86400)
    saat_, kalan = divmod(kalan, 3600)
    dakika, _ = divmod(kalan, 60)
    parcalar = []
    if gun:
        parcalar.append(f"{gun} gün")
    if saat_:
        parcalar.append(f"{saat_} saat")
    parcalar.append(f"{dakika} dakika")
    return " ".join(parcalar)


async def durum_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    ayar = ayarlari_oku()
    acik = ayar.get("otomatik_acik", False)
    g_sayi = len(ayar.get("gruplar", []))
    k_sayi = len(ayar.get("konular", []))
    son = ayar.get("son_bulten", "henüz çalışmadı")
    sure = _sure_metni(datetime.now() - BASLANGIC)
    await update.message.reply_text(
        "🤖 <b>Bot Durumu</b>\n\n"
        f"⏱ Çalışma süresi: {sure}\n"
        f"⏰ Otomatik: {'🟢 açık' if acik else '🔴 kapalı'} (her sabah 09:00)\n"
        f"📌 Seçili: {g_sayi} grup + {k_sayi} konu\n"
        f"📰 Son bülten: {son}\n"
        f"🧠 Model: {MODEL}",
        parse_mode="HTML",
    )


async def buton_tiklandi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not (query.from_user and query.from_user.id == SAHIP_ID):
        await query.answer("Bu bot sana ait değil.", show_alert=True)
        return
    await query.answer()
    veri = query.data

    # Menü / geri: grup listesi
    if veri in ("menu:ozet", "geri"):
        await query.edit_message_text("🔎 Gruplar taranıyor…")
        text, kb = await _grup_listesi_kb()
        if text is None:
            await query.edit_message_text("✅ Okunmamış mesajı olan grup yok. 🎉")
        else:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Kapat
    if veri == "kapat":
        try:
            await query.delete_message()
        except Exception:
            await query.edit_message_text("❌ Kapatıldı.")
        return

    # Otomatik: grup seç/çıkar (normal grup)
    if veri.startswith("oto_sec:"):
        grup_id = int(veri.split(":", 1)[1])
        ayar = ayarlari_oku()
        secili = ayar.get("gruplar", [])
        if grup_id in secili:
            secili.remove(grup_id)
        else:
            secili.append(grup_id)
        ayar["gruplar"] = secili
        ayarlari_yaz(ayar)
        text, kb = await _otomatik_ekrani_kb()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Otomatik: forum grubuna gir (konuları göster)
    if veri.startswith("oto_grp:"):
        grup_id = int(veri.split(":", 1)[1])
        await query.edit_message_text("🔎 Konular taranıyor…")
        text, kb = await _otomatik_konu_kb(grup_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Otomatik: konu seç/çıkar
    if veri.startswith("oto_konu:"):
        _, gid, tid = veri.split(":")
        grup_id, konu_id = int(gid), int(tid)
        ayar = ayarlari_oku()
        konular = [tuple(x) for x in ayar.get("konular", [])]
        if (grup_id, konu_id) in konular:
            konular.remove((grup_id, konu_id))
        else:
            konular.append((grup_id, konu_id))
        ayar["konular"] = [list(x) for x in konular]
        ayarlari_yaz(ayar)
        text, kb = await _otomatik_konu_kb(grup_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Otomatik: konu ekranından ana ekrana dön
    if veri == "oto_geri":
        text, kb = await _otomatik_ekrani_kb()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Otomatik: aç/kapa
    if veri == "oto_durum":
        ayar = ayarlari_oku()
        ayar["otomatik_acik"] = not ayar.get("otomatik_acik", False)
        ayarlari_yaz(ayar)
        text, kb = await _otomatik_ekrani_kb()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Mod seçildi → özetle veya soru-cevap dosyası
    if veri.startswith("mod:"):
        _, key, mod = veri.split(":")
        if mod == "sorucevap":
            await _soru_cevap_dosyasi(query, context, key)
        else:
            await _ozeti_uret_goster(query, key, mod)
        return

    # Gruba tıklandı
    if veri.startswith("grp:"):
        grup_id = int(veri.split(":", 1)[1])
        dialog = await grup_dialog_bul(grup_id)
        if dialog is None:
            await query.edit_message_text("Grup bulunamadı.")
            return

        if is_forum(dialog):
            await query.edit_message_text("🔎 Konular taranıyor…")
            topicler = await topiclari_getir(dialog.entity)
            unread = [t for t in topicler if getattr(t, "unread_count", 0) > 0]
            if not unread:
                await query.edit_message_text(
                    f"✅ <b>{html.escape(dialog.name)}</b> içinde okunmamış konu yok.",
                    parse_mode="HTML",
                )
                return
            butonlar = [
                [InlineKeyboardButton(f"💬 {t.title}  ·  {t.unread_count}",
                                      callback_data=f"top:{grup_id}:{t.id}")]
                for t in unread
            ]
            butonlar.append([
                InlineKeyboardButton("⬅️ Geri", callback_data="geri"), KAPAT_BTN
            ])
            await query.edit_message_text(
                f"🗂 <b>{html.escape(dialog.name)}</b>\n<i>Hangi konuyu özetleyeyim?</i>",
                reply_markup=InlineKeyboardMarkup(butonlar), parse_mode="HTML",
            )
        else:
            await query.edit_message_text("📥 Mesajlar çekiliyor…")
            mesajlar = await okunmamis_mesajlar(dialog)
            await _mod_secimi_goster(
                query, dialog.name, mesajlar, f"okundu:{grup_id}", dialog.unread_count,
                grup_id=grup_id, topic_id=None,
            )

    # Konuya tıklandı
    elif veri.startswith("top:"):
        _, gid, tid = veri.split(":")
        grup_id, topic_id = int(gid), int(tid)
        dialog = await grup_dialog_bul(grup_id)
        if dialog is None:
            await query.edit_message_text("Grup bulunamadı.")
            return
        topicler = await topiclari_getir(dialog.entity)
        topic = next((t for t in topicler if t.id == topic_id), None)
        if topic is None:
            await query.edit_message_text("Konu bulunamadı.")
            return
        await query.edit_message_text("📥 Mesajlar çekiliyor…")
        mesajlar = await topic_unread_mesajlar(dialog.entity, topic)
        baslik = f"{dialog.name} › {topic.title}"
        await _mod_secimi_goster(
            query, baslik, mesajlar, f"oktop:{grup_id}:{topic_id}",
            getattr(topic, "unread_count", None),
            grup_id=grup_id, topic_id=topic_id,
        )

    # Normal grubu okundu yap
    elif veri.startswith("okundu:"):
        grup_id = int(veri.split(":", 1)[1])
        dialog = await grup_dialog_bul(grup_id)
        if dialog is None:
            await query.edit_message_text("Grup bulunamadı.")
            return
        await tele.send_read_acknowledge(dialog.entity)
        eski = query.message.text_html if query.message.text else ""
        await query.edit_message_text(
            eski + "\n\n✅ <b>Okundu olarak işaretlendi.</b>", parse_mode="HTML"
        )

    # Konuyu okundu yap
    elif veri.startswith("oktop:"):
        _, gid, tid = veri.split(":")
        grup_id, topic_id = int(gid), int(tid)
        dialog = await grup_dialog_bul(grup_id)
        if dialog is None:
            await query.edit_message_text("Grup bulunamadı.")
            return
        topicler = await topiclari_getir(dialog.entity)
        topic = next((t for t in topicler if t.id == topic_id), None)
        eski = query.message.text_html if query.message.text else ""
        try:
            read_max = topic.top_message if topic else 0
            await tele(ReadDiscussionRequest(
                peer=dialog.entity, msg_id=topic_id, read_max_id=read_max
            ))
            await query.edit_message_text(
                eski + "\n\n✅ <b>Konu okundu olarak işaretlendi.</b>", parse_mode="HTML"
            )
        except Exception as e:
            await query.edit_message_text(
                eski + f"\n\n⚠️ Okundu işaretlenemedi: {html.escape(str(e))}",
                parse_mode="HTML",
            )


# ======================= Başlatma =======================

async def _post_init(app):
    await app.bot.set_my_commands([
        BotCommand("ozet", "📋 Okunmamış grupları özetle"),
        BotCommand("otomatik", "⏰ Otomatik günlük özet ayarları"),
        BotCommand("durum", "🤖 Bot durumu"),
        BotCommand("start", "👋 Başla / yardım"),
    ])


async def _hata_yakala(update, context):
    """İşlenmeyen handler hatalarını loglar (sessizce çökmesin)."""
    log.error("İşlenmeyen hata: %s", context.error)


def main():
    for ad, deger in [
        ("TG_API_ID", API_ID), ("TG_API_HASH", API_HASH),
        ("GEMINI_API_KEY", GEMINI_API_KEY), ("TG_BOT_TOKEN", BOT_TOKEN),
        ("TG_CHAT_ID", SAHIP_ID),
    ]:
        if not deger:
            print(f"HATA: {ad} ortam değişkeni ayarlı değil.")
            sys.exit(1)

    tele.start()
    print("Telethon hazır. Bot başlatılıyor... (durdurmak için Ctrl+C)")
    log.info("Bot başlatıldı.")

    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ozet", ozet_komut))
    app.add_handler(CommandHandler("otomatik", otomatik_komut))
    app.add_handler(CommandHandler("test_bulten", test_bulten_komut))
    app.add_handler(CommandHandler("durum", durum_komut))
    app.add_handler(CallbackQueryHandler(buton_tiklandi))
    app.add_error_handler(_hata_yakala)

    # Her sabah 09:00'da (Mac'in yerel saatiyle) otomatik bülten
    try:
        from tzlocal import get_localzone
        tz = get_localzone()
    except Exception:
        tz = timezone.utc
    app.job_queue.run_daily(gunluk_bulten_job, time=saat(9, 0, tzinfo=tz))

    app.run_polling()


if __name__ == "__main__":
    main()
