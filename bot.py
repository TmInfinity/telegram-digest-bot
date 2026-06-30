#!/usr/bin/env python3
"""
İnteraktif Telegram özet botu — forum destekli, şık arayüzlü, çok modlu.

Akış: /ozet → grup seç → (forumsa konu seç) → MOD seç → özet.
Modlar: 📝 Genel · 💡 Bilgi & ipucu · 🎯 Aksiyon & görevler
Her özetin altında diğer modlarda tekrar deneme butonları vardır.

Gerekli ortam değişkenleri (.env):
    TG_API_ID, TG_API_HASH, OPENROUTER_API_KEY, TG_BOT_TOKEN, TG_CHAT_ID
    (OPENROUTER_MODEL isteğe bağlı; yoksa varsayılan modele düşer.)
"""

import asyncio
import html
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from datetime import time as saat
from logging.handlers import RotatingFileHandler

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telethon import TelegramClient
from telethon.tl.functions.messages import GetForumTopicsRequest, ReadDiscussionRequest
from telethon.tl.types import (
    ChannelParticipantCreator,
    ChannelParticipantsAdmins,
    ChatParticipantCreator,
)

import i18n
from i18n import t

load_dotenv()  # .env -> ortam değişkenleri (aşağıdaki sabitlerden önce)

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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
SAHIP_ID = int(os.environ.get("TG_CHAT_ID", "0"))

SESSION = "ozet_session"
MAX_MESSAGES = 500
# -------------------------------------------------------------------

tele = TelegramClient(SESSION, API_ID, API_HASH)

# Mod emojileri ( adlar i18n'den gelir: t("mode_<anahtar>"))
MOD_EMOJI = {"genel": "📝", "bilgi": "💡", "aksiyon": "🎯"}
MODLAR = list(MOD_EMOJI)  # mod anahtarlarının sırası


def _mod_ad(mod):
    return t(f"mode_{mod}")

# Boş çıktı için dilden bağımsız sabit işaret (model bunu aynen yazar)
BOS_ISARET = "__EMPTY__"

# Her mod için özet prompt şablonu. İngilizce talimat + {dil} ile çıktı dili enjekte
# edilir (örn. "Turkish"); {baslik} ve {konusma} doldurulur.
MOD_PROMPTLARI = {
    "genel": """Below are the unread messages from the chat "{baslik}".
Write a scannable summary. WRITE THE ENTIRE OUTPUT IN {dil}.

FORMAT:
1) First line: a one-sentence TL;DR starting with "**Summary:**" (translated into {dil}).
2) Then topic by topic: each section heading in **bold**, with "•" bullets under it.
3) If there is a question/request/task addressed DIRECTLY to me, collect them at the
   end under a **bold heading** (translated into {dil}); otherwise omit that section.

RULES:
- Use ONLY information present in the messages. Never invent anything.
- Do not lose dates, times, names, numbers, or links. Keep links verbatim.
- Skip greetings, jokes, "ok/thanks", and filler.
- Be concise; at most ~10 bullets, no repetition.
- For emphasis use ONLY **double asterisks**. Do NOT use #, _, ` or >.

Messages:
{konusma}""",

    "bilgi": """Below are the unread messages from the chat "{baslik}".
Your task: extract ONLY useful/educational content — facts, tips, tactics, resources,
links, recommendations, how-to knowledge. WRITE THE ENTIRE OUTPUT IN {dil}.

FORMAT:
- First line: a one-sentence most-valuable takeaway starting with "**Summary:**" (in {dil}).
- Put useful items under **bold** subheadings as "•" bullets, clear and actionable.
- If there are links/resources, keep them verbatim under a **bold "Resources" heading** (in {dil}).

RULES:
- Completely skip chit-chat, greetings, and jokes.
- Use ONLY what is in the messages, never invent. Write in {dil}.
- For emphasis use ONLY **double asterisks**. Do NOT use #, _, ` or >.
- IF there is no noteworthy useful info, output ONLY this and nothing else: {bos}

Messages:
{konusma}""",

    "aksiyon": """Below are the unread messages from the chat "{baslik}".
Your task: extract ONLY actions for me/us — to-dos, deadlines, appointments, forms,
applications, things to remember, questions awaiting an answer. WRITE EVERYTHING IN {dil}.

FORMAT (only write a section if it has items):
- A **bold "⏰ Dated" heading** (in {dil}) — items with a day/time; put the date first.
- A **bold "📋 Undated" heading** (in {dil}) — to-dos without a date.
Each item as a "•" bullet, short and imperative ("Send X", "Fill out form Y").

RULES:
- Skip general chat, shared info, and filler.
- Use ONLY what is in the messages, never invent. Write in {dil}.
- For emphasis use ONLY **double asterisks**. Do NOT use #, _, ` or >.
- IF there is no noteworthy action/task/date, output ONLY this and nothing else: {bos}

Messages:
{konusma}""",
}

# Otomatik günlük bülten prompt'u (bilgi odaklı, detaylı + kritik mesaj ID'leri)
BULTEN_PROMPT = """Below are the LAST 24 HOURS of messages from the group "{baslik}".
Each message is prefixed with an [ID:number] tag.

Write a DETAILED, INFORMATION-FOCUSED digest. WRITE THE ENTIRE OUTPUT IN {dil}.
Goal: capture the important/educational information shared in this group without missing any.

FORMAT:
- First line: the single most important takeaway of the day, starting with "**Summary:**" (in {dil}).
- Then topic by topic: each section heading in **bold**, with "•" bullets.
- Collect every useful/educational item: tactics, tips, how-to knowledge, strategies,
  resources, links, recommendations, notable data, experiences.
- If multiple people discussed one topic, merge the information and write it clearly.
- If there is a question/request/announcement addressed DIRECTLY to me, note it at the
  end under a **bold heading** (in {dil}). Otherwise omit that section.

RULES:
- Use ONLY what is in the messages, never invent. Write in {dil}.
- Skip unnecessary chat, jokes, greetings, filler. It may be long, but no repetition.
- For emphasis use ONLY **double asterisks**. Do NOT use #, _, ` or >.
- Do NOT write the [ID:..] tags in the text.
- At the very end, on a SEPARATE line, give the ID(s) of the 1-2 most critical messages
  in this exact format (keep the word KRITIK literally):
  KRITIK: 12345, 12389
  If none: KRITIK: yok

Messages:
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
    return {"otomatik_acik": False, "gruplar": [], "konular": [], "dil": "en"}


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
    """Model çıktısından 'KRITIK: ...' satırını ayıklar; (gövde, [id'ler]) döndürür."""
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
        satir.append(t("qa_md_no_content"))


def _soru_cevap_md(baslik, sahip_mesajlari, sorular, topic_id, resim_haritasi):
    """Soru-cevap çiftlerinden (resimler gömülü) Markdown metni üretir."""
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    satir = [t("qa_md_title", baslik=baslik),
             t("qa_md_meta", tarih=tarih, sayi=len(sahip_mesajlari)), ""]
    yanitsiz = []
    cift_sayisi = 0
    for m in sahip_mesajlari:
        h = _yanit_hedefi(m, topic_id)
        if h and h in sorular and sorular[h] is not None:
            q = sorular[h]
            cift_sayisi += 1
            satir.append(t("qa_md_question", ad=gonderen_adi(q)))
            _mesaj_blogu(satir, q, resim_haritasi)
            satir.append("")
            satir.append(t("qa_md_answer"))
            _mesaj_blogu(satir, m, resim_haritasi)
            satir.append("")
            satir.append("---")
            satir.append("")
        else:
            yanitsiz.append(m)
    if yanitsiz:
        satir.append(t("qa_md_unanswered"))
        satir.append("")
        for m in yanitsiz:
            _mesaj_blogu(satir, m, resim_haritasi)
            satir.append("")
    return "\n".join(satir), cift_sayisi


def _konusma_metni(mesajlar):
    return "\n".join(f"{gonderen_adi(m)}: {m.text}" for m in mesajlar)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _ai_cagir(prompt):
    """OpenRouter (OpenAI-uyumlu) üzerinden özetletir; geçici hatalarda yeniden dener.

    SENKRON + bloklayıcı (httpx.post, time.sleep). Async handler'lardan ASLA doğrudan
    çağırma — `asyncio.to_thread(_ai_cagir, ...)` ile thread'e at, yoksa tüm olay
    döngüsü (Telethon dahil) donar. Model `.env`'deki OPENROUTER_MODEL ile değişir.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # OpenRouter'ın isteğe bağlı kimlik başlıkları (sıralamada yardımcı olur):
        "X-Title": "telegram-ozet",
    }
    govde = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    son_hata = None
    for deneme in range(4):
        try:
            r = httpx.post(OPENROUTER_URL, headers=headers, json=govde, timeout=120)
            if r.status_code != 200:
                # 429/503 gibi geçici hataları yeniden dene; kalıcıları yukarı fırlat.
                detay = r.text[:300]
                if r.status_code in (429, 500, 502, 503, 529):
                    raise RuntimeError(f"{r.status_code} geçici hata: {detay}")
                raise RuntimeError(f"OpenRouter {r.status_code}: {detay}")
            veri = r.json()
            if "error" in veri:
                raise RuntimeError(f"OpenRouter hatası: {veri['error']}")
            metin = (veri["choices"][0]["message"].get("content") or "").strip()
            if not metin:
                raise RuntimeError("Model boş yanıt döndürdü.")
            return metin
        except Exception as e:
            son_hata = e
            if deneme < 3:
                time.sleep(3 * (deneme + 1))
    raise son_hata


def ozetle(baslik, konusma, mod):
    prompt = MOD_PROMPTLARI[mod].format(
        baslik=baslik, konusma=konusma,
        dil=i18n.PROMPT_LANG.get(i18n.dil(), "English"), bos=BOS_ISARET,
    )
    return _ai_cagir(prompt)


def _bos_mu(metin):
    s = (metin or "").strip()
    return BOS_ISARET in s and len(s) <= len(BOS_ISARET) + 8


def sadece_sahip(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == SAHIP_ID


def _bicim(metin):
    """Model çıktısını Telegram HTML'e çevirir: ÖNCE güvenli escape, SONRA **kalın**.
    Modelin ürettiği < > & kaçar (injection yok); yalnız bizim **...** dönüşümümüz <b> üretir."""
    g = html.escape(metin or "")
    g = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", g)
    return g


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

def kapat_btn():
    return InlineKeyboardButton(t("btn_close"), callback_data="kapat")


def geri_btn():
    return InlineKeyboardButton(t("btn_back"), callback_data="geri")


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
    butonlar.append([kapat_btn()])
    return t("groups_header"), InlineKeyboardMarkup(butonlar)


def _mod_secim_kb(key):
    """Özet öncesi: 3 mod butonu + Soru-Cevap + Geri/Kapat.
    En son kullanılan mod (ayarlar.json) ⭐ ile işaretlenip en üste alınır."""
    son_mod = ayarlari_oku().get("son_mod")
    sirali = ([son_mod] if son_mod in MODLAR else []) + [m for m in MODLAR if m != son_mod]
    butonlar = []
    for m in sirali:
        yildiz = "⭐ " if m == son_mod else ""
        butonlar.append([InlineKeyboardButton(
            f"{yildiz}{MOD_EMOJI[m]} {_mod_ad(m)}", callback_data=f"mod:{key}:{m}"
        )])
    butonlar.append([InlineKeyboardButton(
        t("btn_qa_file"), callback_data=f"mod:{key}:sorucevap"
    )])
    butonlar.append([geri_btn(), kapat_btn()])
    return InlineKeyboardMarkup(butonlar)


def _diger_modlar_kb(key, aktif_mod, okundu_callback, bos):
    """Özet sonrası: okundu / okundu+kapat / kapat + diğer modlarda tekrar deneme."""
    satirlar = []
    if not bos:
        satirlar.append([
            InlineKeyboardButton(t("btn_mark_read"), callback_data=okundu_callback),
            InlineKeyboardButton(t("btn_mark_read_close"), callback_data=f"okx:{okundu_callback}"),
        ])
    digerler = [m for m in MODLAR if m != aktif_mod]
    satirlar.append([
        InlineKeyboardButton(t("btn_other_mode", ad=_mod_ad(m)), callback_data=f"mod:{key}:{m}")
        for m in digerler
    ])
    if bos:
        satirlar.append([geri_btn(), kapat_btn()])
    else:
        satirlar.append([kapat_btn()])
    return InlineKeyboardMarkup(satirlar)


async def _mod_secimi_goster(query, baslik, mesajlar, okundu_callback, toplam,
                             grup_id=None, topic_id=None):
    """Mesajları önbelleğe alıp mod seçim butonlarını gösterir."""
    if not mesajlar:
        await query.edit_message_text(t("no_text_unread"))
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
        t("pick_action", baslik=html.escape(baslik)),
        reply_markup=_mod_secim_kb(key), parse_mode="HTML",
    )


async def _ozeti_uret_goster(query, key, mod):
    """Önbellekten alıp seçilen modda özetler ve gösterir."""
    veri = ONBELLEK.get(key)
    if veri is None:
        await query.edit_message_text(t("session_expired"))
        return

    emoji, ad = MOD_EMOJI[mod], _mod_ad(mod)
    await query.edit_message_text(t("summarizing", emoji=emoji, ad=ad))
    try:
        ozet = await asyncio.to_thread(ozetle, veri["baslik"], veri["konusma"], mod)
    except Exception as e:
        msg = str(e)
        yeniden = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("btn_retry"), callback_data=f"mod:{key}:{mod}"),
            kapat_btn(),
        ]])
        if any(k in msg for k in ("429", "503", "502", "yoğun", "rate", "high demand")):
            await query.edit_message_text(t("model_busy"), reply_markup=yeniden)
        else:
            await query.edit_message_text(
                t("summarize_failed", hata=html.escape(msg[:300])), reply_markup=yeniden
            )
        return

    # Mod hafızası: bir sonraki sefere bu modu öne çıkar
    try:
        ay = ayarlari_oku()
        ay["son_mod"] = mod
        ayarlari_yaz(ay)
    except Exception:
        pass

    baslik_g = html.escape(veri["baslik"])

    # Boş çıktı: diğer modları öner
    if _bos_mu(ozet):
        kb = _diger_modlar_kb(key, mod, veri["okundu"], bos=True)
        await query.edit_message_text(
            t("mode_empty", baslik=baslik_g, emoji=emoji, ad=ad),
            reply_markup=kb, parse_mode="HTML",
        )
        return

    if veri["toplam"] is not None:
        sayac = t("counter_full", sayi=veri["sayi"], emoji=emoji, ad=ad, toplam=veri["toplam"])
    else:
        sayac = t("counter_simple", sayi=veri["sayi"], emoji=emoji, ad=ad)

    kb = _diger_modlar_kb(key, mod, veri["okundu"], bos=False)
    govde = _bicim(ozet)
    duz = f"📋 <b>{baslik_g}</b>\n\n{govde}{sayac}"
    LIMIT = 3900

    if len(duz) <= LIMIT:
        # Tek mesaja sığıyor: uzunsa gövdeyi katlanabilir alıntıya al (mesaj kısa görünür)
        if len(govde) > 700:
            govde = f"<blockquote expandable>{govde}</blockquote>"
        tam = f"📋 <b>{baslik_g}</b>\n\n{govde}{sayac}"
        await query.edit_message_text(tam, reply_markup=kb, parse_mode="HTML")
        return

    # Çok uzun: katlamadan parçalara böl
    parcalar = _parcala(duz, LIMIT)
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
        await query.edit_message_text(t("session_expired"))
        return
    grup_id = veri.get("grup_id")
    topic_id = veri.get("topic_id")
    baslik = veri["baslik"]

    dialog = await grup_dialog_bul(grup_id)
    if dialog is None:
        await query.edit_message_text(t("group_not_found"))
        return

    await query.edit_message_text(t("qa_detect_owner"))
    owner_id = await grup_sahibi_bul(dialog.entity)
    if owner_id is None:
        await query.edit_message_text(t("qa_owner_not_found"))
        return

    await query.edit_message_text(t("qa_scan_owner"))
    sahip_mesajlari = await _sahip_okunmamis_mesajlar(dialog, topic_id, owner_id)
    if not sahip_mesajlari:
        await query.edit_message_text(t("qa_owner_no_unread"))
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
    await query.edit_message_text(t("qa_downloading_images"))
    indir_listesi = list(sahip_mesajlari) + [q for q in sorular.values() if q is not None]
    resim_haritasi = await _resimleri_indir(indir_listesi, resim_kls)

    await query.edit_message_text(t("qa_preparing_file"))
    md, cift = _soru_cevap_md(baslik, sahip_mesajlari, sorular, topic_id, resim_haritasi)

    dosya = os.path.join(export_kls, f"{guvenli}.md")
    with open(dosya, "w", encoding="utf-8") as f:
        f.write(md)

    # Telegram'dan belge olarak gönder (metin için; resimler bilgisayardaki klasörde)
    await query.edit_message_text(t("qa_sending_file"))
    try:
        with open(dosya, "rb") as f:
            await context.bot.send_document(
                chat_id=SAHIP_ID, document=f, filename=os.path.basename(dosya),
                caption=t("qa_caption", baslik=baslik, cift=cift, sayi=len(sahip_mesajlari)),
            )
    except Exception as e:
        await query.edit_message_text(t("qa_send_failed", hata=html.escape(str(e)[:200])))
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
        t("qa_ready", cift=cift, resim=resim_sayisi, yol=html.escape(export_kls)),
        parse_mode="HTML",
    )


# ======================= Bot komutları =======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(t("btn_get_summary"), callback_data="menu:ozet")
    ]])
    await update.message.reply_text(t("start"), reply_markup=kb, parse_mode="HTML")


async def ozet_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    bekle = await update.message.reply_text(t("scanning_groups"))
    text, kb = await _grup_listesi_kb()
    if text is None:
        await bekle.edit_text(t("no_unread_groups"))
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
            etiket = t("auto_forum_entry", name=g.name)
            if sayi:
                etiket += t("auto_topics_count", n=sayi)
            butonlar.append([InlineKeyboardButton(etiket, callback_data=f"oto_grp:{g.id}")])
        else:
            isaret = "✅" if g.id in secili_gruplar else "⬜"
            butonlar.append([InlineKeyboardButton(
                f"{isaret} 💬 {g.name}", callback_data=f"oto_sec:{g.id}"
            )])

    durum_btn = InlineKeyboardButton(
        t("auto_toggle_on") if acik else t("auto_toggle_off"),
        callback_data="oto_durum",
    )
    butonlar.insert(0, [durum_btn])
    butonlar.append([kapat_btn()])

    durum_yazi = t("auto_on") if acik else t("auto_off")
    metin = t("auto_header", durum=durum_yazi,
              g=len(secili_gruplar), k=len(secili_konular))
    return metin, InlineKeyboardMarkup(butonlar)


async def _otomatik_konu_kb(grup_id):
    """Bir forum grubunun konu seçim ekranı."""
    ayar = ayarlari_oku()
    secili_konular = [tuple(x) for x in ayar.get("konular", [])]

    dialog = await grup_dialog_bul(grup_id)
    if dialog is None:
        return t("group_not_found"), InlineKeyboardMarkup([[kapat_btn()]])

    topicler = await topiclari_getir(dialog.entity)
    butonlar = []
    for tp in topicler:
        isaret = "✅" if (grup_id, tp.id) in secili_konular else "⬜"
        butonlar.append([InlineKeyboardButton(
            f"{isaret} {tp.title}", callback_data=f"oto_konu:{grup_id}:{tp.id}"
        )])
    butonlar.append([
        InlineKeyboardButton(t("btn_back"), callback_data="oto_geri"), kapat_btn()
    ])

    metin = t("auto_topic_header", name=html.escape(dialog.name))
    return metin, InlineKeyboardMarkup(butonlar)


async def otomatik_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    bekle = await update.message.reply_text(t("scanning_groups"))
    metin, kb = await _otomatik_ekrani_kb()
    await bekle.edit_text(metin, reply_markup=kb, parse_mode="HTML")


# ---------------- Otomatik özet (Parça 2: günlük bülten) ----------------

async def _bulten_gonder(bot, baslik, mesajlar, chat_id, topic_id=None):
    """Bir grup/konu için bülten üretip gönderir. Başarılıysa True döndürür."""
    # Son 24 saatte mesaj yoksa kısa not
    if not mesajlar:
        await bot.send_message(
            SAHIP_ID, t("bulletin_no_msgs", baslik=html.escape(baslik)), parse_mode="HTML",
        )
        return False

    konusma = "\n".join(f"[ID:{m.id}] {gonderen_adi(m)}: {m.text}" for m in mesajlar)
    try:
        ham = await asyncio.to_thread(
            _ai_cagir,
            BULTEN_PROMPT.format(
                baslik=baslik, konusma=konusma,
                dil=i18n.PROMPT_LANG.get(i18n.dil(), "English"),
            ),
        )
    except Exception as e:
        await bot.send_message(
            SAHIP_ID,
            t("bulletin_failed", baslik=html.escape(baslik), hata=html.escape(str(e)[:200])),
            parse_mode="HTML",
        )
        return False

    govde, kritik_ids = _kritik_ayikla(ham)

    # Kritik mesaj butonları
    btn_satir = []
    for i, mid in enumerate(kritik_ids, 1):
        etiket = t("btn_critical_single") if len(kritik_ids) == 1 else t("btn_critical_multi", i=i)
        btn_satir.append(InlineKeyboardButton(etiket, url=_msg_link(chat_id, mid, topic_id)))
    kb = InlineKeyboardMarkup([btn_satir]) if btn_satir else None

    govde_h = _bicim(govde)
    baslik_h = html.escape(baslik)
    duz = f"📰 <b>{baslik_h}</b>\n\n{govde_h}"
    LIMIT = 3900
    if len(duz) <= LIMIT:
        # Tek mesaja sığıyor: uzunsa gövdeyi katlanabilir alıntıya al
        govde_g = f"<blockquote expandable>{govde_h}</blockquote>" if len(govde_h) > 700 else govde_h
        parcalar = [f"📰 <b>{baslik_h}</b>\n\n{govde_g}"]
    else:
        parcalar = _parcala(duz, LIMIT)

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
        await bot.send_message(SAHIP_ID, t("no_groups_selected"))
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


# Aynı anda iki bülten çalışmasını önler (09:00 job'u + telafi job'u yarışı)
_bulten_lock = asyncio.Lock()


async def _gunluk_bulten_tetikle(bot, telafi):
    """Bugünün otomatik bültenini (henüz çalışmadıysa) çalıştırır.
    Kalıcı 'son_bulten_tarih' sayesinde günde yalnız bir kez çalışır.
    telafi=True iken yalnız 09:00'dan sonra tetiklenir (uyandıktan sonra telafi)."""
    async with _bulten_lock:
        ayar = ayarlari_oku()
        if not ayar.get("otomatik_acik"):
            return
        bugun = datetime.now().date().isoformat()
        if ayar.get("son_bulten_tarih") == bugun:
            return  # bugün zaten çalıştı
        if telafi and datetime.now().hour < 9:
            return  # telafi sabah 09:00'dan önce çalışmasın
        # Tarihi ÖNCEDEN işaretle: hata olsa bile gün boyu tekrar tekrar denemesin.
        ay = ayarlari_oku()
        ay["son_bulten_tarih"] = bugun
        ayarlari_yaz(ay)
        log.info("Otomatik bülten tetiklendi (telafi=%s).", telafi)
        await _bulteni_calistir(bot, zorla=False)


async def gunluk_bulten_job(context: ContextTypes.DEFAULT_TYPE):
    """Her sabah tam 09:00'da çalışır (Mac uyanıksa)."""
    await _gunluk_bulten_tetikle(context.bot, telafi=False)


async def bulten_telafi_job(context: ContextTypes.DEFAULT_TYPE):
    """Telafi: Mac 09:00'da uyuyorsa, uyandıktan sonraki ilk tetiklemede bugünün
    bülteni çalışmadıysa hemen çalıştırır (sık aralıklı kontrol)."""
    await _gunluk_bulten_tetikle(context.bot, telafi=True)


async def test_bulten_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    await update.message.reply_text(t("test_running"))
    await _bulteni_calistir(context.bot, zorla=True)
    await update.message.reply_text(t("test_done"))


def _sure_metni(delta):
    """timedelta'yı okunur süre metnine çevirir (dile göre)."""
    saniye = int(delta.total_seconds())
    gun, kalan = divmod(saniye, 86400)
    saat_, kalan = divmod(kalan, 3600)
    dakika, _ = divmod(kalan, 60)
    parcalar = []
    if gun:
        parcalar.append(t("dur_days", n=gun))
    if saat_:
        parcalar.append(t("dur_hours", n=saat_))
    parcalar.append(t("dur_minutes", n=dakika))
    return " ".join(parcalar)


async def durum_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    ayar = ayarlari_oku()
    acik = ayar.get("otomatik_acik", False)
    son = ayar.get("son_bulten") or t("last_never")
    await update.message.reply_text(
        t("status",
          sure=_sure_metni(datetime.now() - BASLANGIC),
          durum=t("auto_on") if acik else t("auto_off"),
          g=len(ayar.get("gruplar", [])),
          k=len(ayar.get("konular", [])),
          son=html.escape(str(son)),
          lang=i18n.LANGS.get(i18n.dil(), i18n.dil()),
          model=html.escape(OPENROUTER_MODEL)),
        parse_mode="HTML",
    )


async def _okundu_isaretle(inner):
    """inner: 'okundu:<gid>' veya 'oktop:<gid>:<tid>'. Okundu yapar; (ok, hata) döndürür."""
    parts = inner.split(":")
    dialog = await grup_dialog_bul(int(parts[1]))
    if dialog is None:
        return False, t("group_not_found")
    try:
        if parts[0] == "okundu":
            await tele.send_read_acknowledge(dialog.entity)
        else:  # oktop
            topic_id = int(parts[2])
            topicler = await topiclari_getir(dialog.entity)
            topic = next((tp for tp in topicler if tp.id == topic_id), None)
            read_max = topic.top_message if topic else 0
            await tele(ReadDiscussionRequest(
                peer=dialog.entity, msg_id=topic_id, read_max_id=read_max
            ))
        return True, None
    except Exception as e:
        return False, str(e)


async def buton_tiklandi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not (query.from_user and query.from_user.id == SAHIP_ID):
        await query.answer(t("not_your_bot"), show_alert=True)
        return
    await query.answer()
    veri = query.data

    # Menü / geri: grup listesi
    if veri in ("menu:ozet", "geri"):
        await query.edit_message_text(t("scanning_groups"))
        metin, kb = await _grup_listesi_kb()
        if metin is None:
            await query.edit_message_text(t("no_unread_groups"))
        else:
            await query.edit_message_text(metin, reply_markup=kb, parse_mode="HTML")
        return

    # Kapat
    if veri == "kapat":
        try:
            await query.delete_message()
        except Exception:
            await query.edit_message_text(t("closed"))
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
        await query.edit_message_text(t("scanning_topics"))
        metin, kb = await _otomatik_konu_kb(grup_id)
        await query.edit_message_text(metin, reply_markup=kb, parse_mode="HTML")
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
            await query.edit_message_text(t("group_not_found"))
            return

        if is_forum(dialog):
            await query.edit_message_text(t("scanning_topics"))
            topicler = await topiclari_getir(dialog.entity)
            unread = [tp for tp in topicler if getattr(tp, "unread_count", 0) > 0]
            if not unread:
                await query.edit_message_text(
                    t("no_unread_topics", name=html.escape(dialog.name)), parse_mode="HTML",
                )
                return
            butonlar = [
                [InlineKeyboardButton(t("topic_btn", title=tp.title, n=tp.unread_count),
                                      callback_data=f"top:{grup_id}:{tp.id}")]
                for tp in unread
            ]
            butonlar.append([geri_btn(), kapat_btn()])
            await query.edit_message_text(
                t("topic_pick_header", name=html.escape(dialog.name)),
                reply_markup=InlineKeyboardMarkup(butonlar), parse_mode="HTML",
            )
        else:
            await query.edit_message_text(t("fetching_msgs"))
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
            await query.edit_message_text(t("group_not_found"))
            return
        topicler = await topiclari_getir(dialog.entity)
        topic = next((tp for tp in topicler if tp.id == topic_id), None)
        if topic is None:
            await query.edit_message_text(t("topic_not_found"))
            return
        await query.edit_message_text(t("fetching_msgs"))
        mesajlar = await topic_unread_mesajlar(dialog.entity, topic)
        baslik = f"{dialog.name} › {topic.title}"
        await _mod_secimi_goster(
            query, baslik, mesajlar, f"oktop:{grup_id}:{topic_id}",
            getattr(topic, "unread_count", None),
            grup_id=grup_id, topic_id=topic_id,
        )

    # Okundu yap (mesajı koru, alta not ekle)
    elif veri.startswith("okundu:") or veri.startswith("oktop:"):
        ok, hata = await _okundu_isaretle(veri)
        eski = query.message.text_html if query.message.text else ""
        if ok:
            await query.edit_message_text(eski + t("marked_read"), parse_mode="HTML")
        else:
            await query.edit_message_text(
                eski + t("mark_read_failed", hata=html.escape(hata)), parse_mode="HTML",
            )

    # Okundu & kapat (mesajı sil)
    elif veri.startswith("okx:"):
        ok, hata = await _okundu_isaretle(veri[4:])
        if ok:
            try:
                await query.delete_message()
            except Exception:
                await query.edit_message_text(t("marked_read").strip())
        else:
            eski = query.message.text_html if query.message.text else ""
            await query.edit_message_text(
                eski + t("mark_read_failed", hata=html.escape(hata)), parse_mode="HTML",
            )

    # Dil seçildi
    elif veri.startswith("setdil:"):
        yeni = veri.split(":", 1)[1]
        if yeni in i18n.LANGS:
            i18n.set_dil(yeni)
            ay = ayarlari_oku()
            ay["dil"] = yeni
            ayarlari_yaz(ay)
            await _post_init(context.application)  # komut açıklamalarını da güncelle
            await query.edit_message_text(
                t("lang_changed", lang=i18n.LANGS[yeni]), parse_mode="HTML"
            )


# ======================= Başlatma =======================

async def dil_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sadece_sahip(update):
        return
    simdiki = i18n.dil()
    butonlar = [
        [InlineKeyboardButton(
            ("✅ " if kod == simdiki else "") + ad, callback_data=f"setdil:{kod}"
        )]
        for kod, ad in i18n.LANGS.items()
    ]
    butonlar.append([kapat_btn()])
    await update.message.reply_text(
        t("lang_header"), reply_markup=InlineKeyboardMarkup(butonlar), parse_mode="HTML",
    )


async def _post_init(app):
    await app.bot.set_my_commands([
        BotCommand("ozet", t("cmd_ozet")),
        BotCommand("otomatik", t("cmd_otomatik")),
        BotCommand("dil", t("cmd_dil")),
        BotCommand("durum", t("cmd_durum")),
        BotCommand("start", t("cmd_start")),
    ])


async def _hata_yakala(update, context):
    """İşlenmeyen handler hatalarını loglar (sessizce çökmesin)."""
    log.error("İşlenmeyen hata: %s", context.error)


def main():
    for ad, deger in [
        ("TG_API_ID", API_ID), ("TG_API_HASH", API_HASH),
        ("OPENROUTER_API_KEY", OPENROUTER_API_KEY), ("TG_BOT_TOKEN", BOT_TOKEN),
        ("TG_CHAT_ID", SAHIP_ID),
    ]:
        if not deger:
            print(f"HATA: {ad} ortam değişkeni ayarlı değil.")
            sys.exit(1)

    # Kayıtlı dili yükle (varsayılan: en)
    i18n.set_dil(ayarlari_oku().get("dil", "en"))

    tele.start()
    print("Telethon hazır. Bot başlatılıyor... (durdurmak için Ctrl+C)")
    log.info("Bot başlatıldı.")

    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ozet", ozet_komut))
    app.add_handler(CommandHandler("otomatik", otomatik_komut))
    app.add_handler(CommandHandler("test_bulten", test_bulten_komut))
    app.add_handler(CommandHandler("dil", dil_komut))
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

    # Telafi: Mac 09:00'da uykudaysa, uyandıktan sonra ilk kontrolde bugünün bülteni
    # çalışmadıysa hemen çalıştırır. misfire_grace_time, uyku sırasında kaçan tetiği
    # uyanışta hemen ateşler. Çalışıp çalışmama kararını _gunluk_bulten_tetikle verir.
    app.job_queue.run_repeating(
        bulten_telafi_job, interval=120, first=30,
        job_kwargs={"misfire_grace_time": 3600, "coalesce": True},
    )

    app.run_polling()


if __name__ == "__main__":
    main()
