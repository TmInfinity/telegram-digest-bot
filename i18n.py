#!/usr/bin/env python3
"""
Çok dilli metinler (i18n) — kullanıcı arayüzü dizgeleri ve dil yardımcıları.

Diller: en (İngilizce), tr (Türkçe), ru (Rusça), tk (Türkmençe).
Kullanım: i18n.set_dil("ru"); i18n.t("anahtar", ad="...") -> o dildeki metin.
Eksik anahtar/dil otomatik İngilizce'ye düşer. Çeviri kalitesi için tk (Türkmençe)
geliştirici tarafından gözden geçirilmelidir.
"""

# Dil seçici menüsünde gösterilecek isimler (her dil kendi adıyla)
LANGS = {
    "en": "English",
    "tr": "Türkçe",
    "ru": "Русский",
    "tk": "Türkmençe",
}

# AI prompt'una enjekte edilen çıktı dili adı (İngilizce isimle)
PROMPT_LANG = {
    "en": "English",
    "tr": "Turkish",
    "ru": "Russian",
    "tk": "Turkmen",
}

_current = "en"


def set_dil(lang):
    global _current
    if lang in STRINGS:
        _current = lang


def dil():
    return _current


def t(key, **kw):
    d = STRINGS.get(_current, STRINGS["en"])
    s = d.get(key)
    if s is None:
        s = STRINGS["en"].get(key, key)
    return s.format(**kw) if kw else s


STRINGS = {
    # ================================ ENGLISH ================================
    "en": {
        "btn_get_summary": "📋 Get summary",
        "btn_qa_file": "📄 Q&A file",
        "btn_back": "⬅️ Back",
        "btn_close": "❌ Close",
        "btn_mark_read": "✅ Mark read",
        "btn_mark_read_close": "✅ Read & close",
        "btn_retry": "🔄 Retry",
        "btn_other_mode": "🔄 {ad}",
        "btn_critical_single": "🔗 Go to key message",
        "btn_critical_multi": "🔗 Key #{i}",

        "mode_genel": "General",
        "mode_bilgi": "Knowledge & tips",
        "mode_aksiyon": "Action & tasks",

        "start": (
            "👋 <b>Message Summarizer</b>\n\n"
            "I summarize your unread groups and forum topics.\n\n"
            "📋  <b>Get summary</b> — lists groups with unread messages\n"
            "👆  Group → (topic) → pick a mode → summary\n"
            "✅  Clear with <b>Mark read</b>\n\n"
            "Modes: 📝 General · 💡 Knowledge & tips · 🎯 Action\n\n"
            "Tap the button below or use /ozet."
        ),

        "scanning_groups": "🔎 Scanning groups…",
        "scanning_topics": "🔎 Scanning topics…",
        "fetching_msgs": "📥 Fetching messages…",
        "no_unread_groups": "✅ No groups with unread messages. 🎉",
        "groups_header": (
            "📋 <b>Unread Groups</b>\n"
            "<i>Which one should I summarize?</i>\n"
            "<i>🗂 forum group · 💬 normal group</i>"
        ),
        "group_not_found": "Group not found.",
        "topic_not_found": "Topic not found.",
        "no_text_unread": "ℹ️ No unread text messages found.",
        "pick_action": "📋 <b>{baslik}</b>\n<i>What should I do?</i>",
        "no_unread_topics": "✅ No unread topics in <b>{name}</b>.",
        "topic_pick_header": "🗂 <b>{name}</b>\n<i>Which topic should I summarize?</i>",
        "topic_btn": "💬 {title}  ·  {n}",

        "session_expired": "⌛ This summary session has expired. Start again with /ozet.",
        "summarizing": "🤖 Summarizing… ({emoji} {ad})",
        "model_busy": "⚠️ The model is busy right now. Try again shortly.",
        "summarize_failed": "⚠️ Could not summarize: {hata}",
        "mode_empty": (
            "📋 <b>{baslik}</b>\n\n"
            "ℹ️ <i>Nothing noteworthy in this mode ({emoji} {ad}).</i>\n"
            "Want to try another mode?"
        ),
        "counter_full": "\n\n━━━━━━━━━\n📊 {sayi} text messages · {emoji} {ad} · {toplam} unread total",
        "counter_simple": "\n\n━━━━━━━━━\n📊 {sayi} text messages · {emoji} {ad}",

        "marked_read": "\n\n✅ <b>Marked as read.</b>",
        "mark_read_failed": "\n\n⚠️ Could not mark as read: {hata}",
        "closed": "❌ Closed.",
        "not_your_bot": "This bot isn't yours.",

        # Q&A export
        "qa_detect_owner": "🔎 Detecting group owner…",
        "qa_owner_not_found": (
            "⚠️ Could not detect the group owner (creator). "
            "Q&A export isn't possible for this group."
        ),
        "qa_scan_owner": "📥 Scanning the group owner's messages…",
        "qa_owner_no_unread": "ℹ️ The group owner has no unread messages.",
        "qa_downloading_images": "🖼 Downloading images…",
        "qa_preparing_file": "📝 Preparing the file…",
        "qa_sending_file": "📤 Sending the file…",
        "qa_send_failed": "⚠️ Could not send the file: {hata}",
        "qa_caption": "📄 {baslik} — {cift} Q&A, {sayi} messages",
        "qa_ready": (
            "✅ <b>Q&A file ready</b>\n"
            "📄 {cift} Q&A pairs · 🖼 {resim} images\n"
            "<i>To see the images, open this folder on your computer:</i>\n"
            "<code>{yol}</code>"
        ),
        "qa_md_title": "# Q&A — {baslik}",
        "qa_md_meta": "_{tarih} · {sayi} answers_",
        "qa_md_question": "### ❓ {ad}",
        "qa_md_answer": "**💬 Answer:**",
        "qa_md_unanswered": "## Messages without a reply",
        "qa_md_no_content": "(no content)",

        # Auto digest
        "auto_header": (
            "⏰ <b>Automatic Daily Digest</b>\n"
            "Status: {durum} · Every morning at 09:00\n"
            "Selected: {g} groups + {k} topics\n\n"
            "<i>💬 normal group: tap = select · 🗂 forum: tap = open topics</i>"
        ),
        "auto_on": "🟢 on",
        "auto_off": "🔴 off",
        "auto_toggle_on": "🟢 Auto: ON (turn off)",
        "auto_toggle_off": "🔴 Auto: OFF (turn on)",
        "auto_forum_entry": "🗂 {name}  ▶︎",
        "auto_topics_count": "  ({n} topics selected)",
        "auto_topic_header": "🗂 <b>{name}</b>\n<i>Pick the topics to include in the digest.</i>",

        # Bulletin
        "bulletin_no_msgs": "📰 <b>{baslik}</b>\n\nℹ️ No messages in the last 24h.",
        "bulletin_failed": "📰 <b>{baslik}</b>\n\n⚠️ Could not summarize: {hata}",
        "no_groups_selected": "ℹ️ No groups/topics selected for the digest. Use /otomatik to select.",
        "test_running": "🧪 Running the test digest… (may take a moment)",
        "test_done": "✅ Test digest finished.",

        # Status
        "status": (
            "🤖 <b>Bot Status</b>\n\n"
            "⏱ Uptime: {sure}\n"
            "⏰ Auto: {durum} (every morning at 09:00)\n"
            "📌 Selected: {g} groups + {k} topics\n"
            "📰 Last digest: {son}\n"
            "🌍 Language: {lang}\n"
            "🧠 Model: {model}"
        ),
        "last_never": "not run yet",
        "dur_days": "{n} days",
        "dur_hours": "{n} h",
        "dur_minutes": "{n} min",

        # Language
        "lang_header": "🌍 <b>Language</b>\nChoose the interface and summary language:",
        "lang_changed": "✅ Language set to <b>{lang}</b>.",

        # Command descriptions
        "cmd_ozet": "📋 Summarize unread groups",
        "cmd_otomatik": "⏰ Automatic daily digest settings",
        "cmd_dil": "🌍 Change language",
        "cmd_durum": "🤖 Bot status",
        "cmd_start": "👋 Start / help",
    },

    # ================================ TÜRKÇE ================================
    "tr": {
        "btn_get_summary": "📋 Özet Al",
        "btn_qa_file": "📄 Soru-Cevap dosyası",
        "btn_back": "⬅️ Geri",
        "btn_close": "❌ Kapat",
        "btn_mark_read": "✅ Okundu yap",
        "btn_mark_read_close": "✅ Okundu & kapat",
        "btn_retry": "🔄 Tekrar dene",
        "btn_other_mode": "🔄 {ad}",
        "btn_critical_single": "🔗 Önemli mesaja git",
        "btn_critical_multi": "🔗 Önemli #{i}",

        "mode_genel": "Genel özet",
        "mode_bilgi": "Bilgi & ipucu",
        "mode_aksiyon": "Aksiyon & görevler",

        "start": (
            "👋 <b>Mesaj Özetleyici</b>\n\n"
            "Okunmamış grup ve forum konularını senin için özetlerim.\n\n"
            "📋  <b>Özet Al</b> — okunmamış grupları listeler\n"
            "👆  Grup → (konu) → mod seç → özet\n"
            "✅  <b>Okundu yap</b> ile temizle\n\n"
            "Modlar: 📝 Genel · 💡 Bilgi & ipucu · 🎯 Aksiyon\n\n"
            "Alttaki butona ya da /ozet komutuna bas."
        ),

        "scanning_groups": "🔎 Gruplar taranıyor…",
        "scanning_topics": "🔎 Konular taranıyor…",
        "fetching_msgs": "📥 Mesajlar çekiliyor…",
        "no_unread_groups": "✅ Okunmamış mesajı olan grup yok. 🎉",
        "groups_header": (
            "📋 <b>Okunmamış Gruplar</b>\n"
            "<i>Hangisini özetleyeyim?</i>\n"
            "<i>🗂 konulu grup · 💬 normal grup</i>"
        ),
        "group_not_found": "Grup bulunamadı.",
        "topic_not_found": "Konu bulunamadı.",
        "no_text_unread": "ℹ️ Metinli okunmamış mesaj bulunamadı.",
        "pick_action": "📋 <b>{baslik}</b>\n<i>Ne yapayım?</i>",
        "no_unread_topics": "✅ <b>{name}</b> içinde okunmamış konu yok.",
        "topic_pick_header": "🗂 <b>{name}</b>\n<i>Hangi konuyu özetleyeyim?</i>",
        "topic_btn": "💬 {title}  ·  {n}",

        "session_expired": "⌛ Bu özet oturumu artık geçerli değil. /ozet ile tekrar başla.",
        "summarizing": "🤖 Özetleniyor… ({emoji} {ad})",
        "model_busy": "⚠️ Model şu an yoğun. Biraz sonra tekrar dene.",
        "summarize_failed": "⚠️ Özetlenemedi: {hata}",
        "mode_empty": (
            "📋 <b>{baslik}</b>\n\n"
            "ℹ️ <i>Bu modda ({emoji} {ad}) kayda değer bir şey çıkmadı.</i>\n"
            "Başka bir modda denemek ister misin?"
        ),
        "counter_full": "\n\n━━━━━━━━━\n📊 {sayi} metin mesajı · {emoji} {ad} · toplam {toplam} okunmamış",
        "counter_simple": "\n\n━━━━━━━━━\n📊 {sayi} metin mesajı · {emoji} {ad}",

        "marked_read": "\n\n✅ <b>Okundu olarak işaretlendi.</b>",
        "mark_read_failed": "\n\n⚠️ Okundu işaretlenemedi: {hata}",
        "closed": "❌ Kapatıldı.",
        "not_your_bot": "Bu bot sana ait değil.",

        "qa_detect_owner": "🔎 Grup sahibi tespit ediliyor…",
        "qa_owner_not_found": (
            "⚠️ Grup sahibi (kurucu) tespit edilemedi. "
            "Bu grup için soru-cevap çıkarımı yapamıyorum."
        ),
        "qa_scan_owner": "📥 Grup sahibinin mesajları taranıyor…",
        "qa_owner_no_unread": "ℹ️ Grup sahibinin okunmamış mesajı yok.",
        "qa_downloading_images": "🖼 Resimler indiriliyor…",
        "qa_preparing_file": "📝 Dosya hazırlanıyor…",
        "qa_sending_file": "📤 Dosya gönderiliyor…",
        "qa_send_failed": "⚠️ Dosya gönderilemedi: {hata}",
        "qa_caption": "📄 {baslik} — {cift} soru-cevap, {sayi} mesaj",
        "qa_ready": (
            "✅ <b>Soru-Cevap dosyası hazır</b>\n"
            "📄 {cift} soru-cevap çifti · 🖼 {resim} resim\n"
            "<i>Resimleri görmek için bilgisayarında bu klasörü aç:</i>\n"
            "<code>{yol}</code>"
        ),
        "qa_md_title": "# Soru-Cevap — {baslik}",
        "qa_md_meta": "_{tarih} · {sayi} cevap_",
        "qa_md_question": "### ❓ {ad}",
        "qa_md_answer": "**💬 Cevap:**",
        "qa_md_unanswered": "## Yanıt olmayan mesajlar",
        "qa_md_no_content": "(içerik yok)",

        "auto_header": (
            "⏰ <b>Otomatik Günlük Özet</b>\n"
            "Durum: {durum} · Her sabah 09:00\n"
            "Seçili: {g} grup + {k} konu\n\n"
            "<i>💬 normal grup: dokun = seç · 🗂 forum: dokun = konulara gir</i>"
        ),
        "auto_on": "🟢 açık",
        "auto_off": "🔴 kapalı",
        "auto_toggle_on": "🟢 Otomatik: AÇIK (kapat)",
        "auto_toggle_off": "🔴 Otomatik: KAPALI (aç)",
        "auto_forum_entry": "🗂 {name}  ▶︎",
        "auto_topics_count": "  ({n} konu seçili)",
        "auto_topic_header": "🗂 <b>{name}</b>\n<i>Otomatiğe almak istediğin konuları seç.</i>",

        "bulletin_no_msgs": "📰 <b>{baslik}</b>\n\nℹ️ Son 24 saatte mesaj yok.",
        "bulletin_failed": "📰 <b>{baslik}</b>\n\n⚠️ Özetlenemedi: {hata}",
        "no_groups_selected": "ℹ️ Otomatik özet için hiç grup/konu seçili değil. /otomatik ile seç.",
        "test_running": "🧪 Test bülteni çalıştırılıyor… (biraz sürebilir)",
        "test_done": "✅ Test bülteni tamamlandı.",

        "status": (
            "🤖 <b>Bot Durumu</b>\n\n"
            "⏱ Çalışma süresi: {sure}\n"
            "⏰ Otomatik: {durum} (her sabah 09:00)\n"
            "📌 Seçili: {g} grup + {k} konu\n"
            "📰 Son bülten: {son}\n"
            "🌍 Dil: {lang}\n"
            "🧠 Model: {model}"
        ),
        "last_never": "henüz çalışmadı",
        "dur_days": "{n} gün",
        "dur_hours": "{n} saat",
        "dur_minutes": "{n} dakika",

        "lang_header": "🌍 <b>Dil</b>\nArayüz ve özet dilini seç:",
        "lang_changed": "✅ Dil <b>{lang}</b> olarak ayarlandı.",

        "cmd_ozet": "📋 Okunmamış grupları özetle",
        "cmd_otomatik": "⏰ Otomatik günlük özet ayarları",
        "cmd_dil": "🌍 Dili değiştir",
        "cmd_durum": "🤖 Bot durumu",
        "cmd_start": "👋 Başla / yardım",
    },

    # ================================ РУССКИЙ ================================
    "ru": {
        "btn_get_summary": "📋 Сводка",
        "btn_qa_file": "📄 Файл вопрос-ответ",
        "btn_back": "⬅️ Назад",
        "btn_close": "❌ Закрыть",
        "btn_mark_read": "✅ Прочитано",
        "btn_mark_read_close": "✅ Прочитать и закрыть",
        "btn_retry": "🔄 Повторить",
        "btn_other_mode": "🔄 {ad}",
        "btn_critical_single": "🔗 К важному сообщению",
        "btn_critical_multi": "🔗 Важное #{i}",

        "mode_genel": "Общая",
        "mode_bilgi": "Знания и советы",
        "mode_aksiyon": "Задачи и действия",

        "start": (
            "👋 <b>Сводка сообщений</b>\n\n"
            "Я делаю сводку непрочитанных групп и тем форума.\n\n"
            "📋  <b>Сводка</b> — список групп с непрочитанными\n"
            "👆  Группа → (тема) → выбор режима → сводка\n"
            "✅  Очистить кнопкой <b>Прочитано</b>\n\n"
            "Режимы: 📝 Общая · 💡 Знания и советы · 🎯 Задачи\n\n"
            "Нажми кнопку ниже или команду /ozet."
        ),

        "scanning_groups": "🔎 Сканирую группы…",
        "scanning_topics": "🔎 Сканирую темы…",
        "fetching_msgs": "📥 Загружаю сообщения…",
        "no_unread_groups": "✅ Нет групп с непрочитанными сообщениями. 🎉",
        "groups_header": (
            "📋 <b>Непрочитанные группы</b>\n"
            "<i>Какую сделать сводку?</i>\n"
            "<i>🗂 форум-группа · 💬 обычная группа</i>"
        ),
        "group_not_found": "Группа не найдена.",
        "topic_not_found": "Тема не найдена.",
        "no_text_unread": "ℹ️ Непрочитанных текстовых сообщений не найдено.",
        "pick_action": "📋 <b>{baslik}</b>\n<i>Что сделать?</i>",
        "no_unread_topics": "✅ В <b>{name}</b> нет непрочитанных тем.",
        "topic_pick_header": "🗂 <b>{name}</b>\n<i>Сводку какой темы сделать?</i>",
        "topic_btn": "💬 {title}  ·  {n}",

        "session_expired": "⌛ Эта сессия сводки больше недействительна. Начни заново через /ozet.",
        "summarizing": "🤖 Делаю сводку… ({emoji} {ad})",
        "model_busy": "⚠️ Модель сейчас перегружена. Повтори чуть позже.",
        "summarize_failed": "⚠️ Не удалось сделать сводку: {hata}",
        "mode_empty": (
            "📋 <b>{baslik}</b>\n\n"
            "ℹ️ <i>В этом режиме ({emoji} {ad}) ничего значимого нет.</i>\n"
            "Попробовать другой режим?"
        ),
        "counter_full": "\n\n━━━━━━━━━\n📊 {sayi} текст. сообщений · {emoji} {ad} · всего непрочитано {toplam}",
        "counter_simple": "\n\n━━━━━━━━━\n📊 {sayi} текст. сообщений · {emoji} {ad}",

        "marked_read": "\n\n✅ <b>Отмечено как прочитанное.</b>",
        "mark_read_failed": "\n\n⚠️ Не удалось отметить прочитанным: {hata}",
        "closed": "❌ Закрыто.",
        "not_your_bot": "Этот бот не ваш.",

        "qa_detect_owner": "🔎 Определяю владельца группы…",
        "qa_owner_not_found": (
            "⚠️ Не удалось определить владельца (создателя) группы. "
            "Извлечение вопрос-ответ для этой группы невозможно."
        ),
        "qa_scan_owner": "📥 Сканирую сообщения владельца группы…",
        "qa_owner_no_unread": "ℹ️ У владельца группы нет непрочитанных сообщений.",
        "qa_downloading_images": "🖼 Загружаю изображения…",
        "qa_preparing_file": "📝 Готовлю файл…",
        "qa_sending_file": "📤 Отправляю файл…",
        "qa_send_failed": "⚠️ Не удалось отправить файл: {hata}",
        "qa_caption": "📄 {baslik} — {cift} вопрос-ответ, {sayi} сообщений",
        "qa_ready": (
            "✅ <b>Файл вопрос-ответ готов</b>\n"
            "📄 {cift} пар вопрос-ответ · 🖼 {resim} изображений\n"
            "<i>Чтобы увидеть изображения, открой эту папку на компьютере:</i>\n"
            "<code>{yol}</code>"
        ),
        "qa_md_title": "# Вопрос-ответ — {baslik}",
        "qa_md_meta": "_{tarih} · {sayi} ответов_",
        "qa_md_question": "### ❓ {ad}",
        "qa_md_answer": "**💬 Ответ:**",
        "qa_md_unanswered": "## Сообщения без ответа",
        "qa_md_no_content": "(нет содержимого)",

        "auto_header": (
            "⏰ <b>Автоматическая ежедневная сводка</b>\n"
            "Статус: {durum} · Каждое утро в 09:00\n"
            "Выбрано: {g} групп + {k} тем\n\n"
            "<i>💬 обычная группа: тап = выбрать · 🗂 форум: тап = открыть темы</i>"
        ),
        "auto_on": "🟢 вкл",
        "auto_off": "🔴 выкл",
        "auto_toggle_on": "🟢 Авто: ВКЛ (выключить)",
        "auto_toggle_off": "🔴 Авто: ВЫКЛ (включить)",
        "auto_forum_entry": "🗂 {name}  ▶︎",
        "auto_topics_count": "  (выбрано тем: {n})",
        "auto_topic_header": "🗂 <b>{name}</b>\n<i>Выбери темы для сводки.</i>",

        "bulletin_no_msgs": "📰 <b>{baslik}</b>\n\nℹ️ За последние 24 часа нет сообщений.",
        "bulletin_failed": "📰 <b>{baslik}</b>\n\n⚠️ Не удалось сделать сводку: {hata}",
        "no_groups_selected": "ℹ️ Для сводки не выбрано ни одной группы/темы. Используй /otomatik.",
        "test_running": "🧪 Запускаю тестовую сводку… (может занять время)",
        "test_done": "✅ Тестовая сводка завершена.",

        "status": (
            "🤖 <b>Статус бота</b>\n\n"
            "⏱ Время работы: {sure}\n"
            "⏰ Авто: {durum} (каждое утро в 09:00)\n"
            "📌 Выбрано: {g} групп + {k} тем\n"
            "📰 Последняя сводка: {son}\n"
            "🌍 Язык: {lang}\n"
            "🧠 Модель: {model}"
        ),
        "last_never": "ещё не запускалась",
        "dur_days": "{n} дн.",
        "dur_hours": "{n} ч.",
        "dur_minutes": "{n} мин.",

        "lang_header": "🌍 <b>Язык</b>\nВыбери язык интерфейса и сводок:",
        "lang_changed": "✅ Язык установлен: <b>{lang}</b>.",

        "cmd_ozet": "📋 Сводка непрочитанных групп",
        "cmd_otomatik": "⏰ Настройки авто-сводки",
        "cmd_dil": "🌍 Сменить язык",
        "cmd_durum": "🤖 Статус бота",
        "cmd_start": "👋 Старт / помощь",
    },

    # ============================== TÜRKMENÇE ==============================
    "tk": {
        "btn_get_summary": "📋 Gysgaça mazmun",
        "btn_qa_file": "📄 Sorag-jogap faýly",
        "btn_back": "⬅️ Yza",
        "btn_close": "❌ Ýap",
        "btn_mark_read": "✅ Okaldy belle",
        "btn_mark_read_close": "✅ Okaldy & ýap",
        "btn_retry": "🔄 Gaýtadan synanyş",
        "btn_other_mode": "🔄 {ad}",
        "btn_critical_single": "🔗 Möhüm habara git",
        "btn_critical_multi": "🔗 Möhüm #{i}",

        "mode_genel": "Umumy",
        "mode_bilgi": "Bilim & maslahat",
        "mode_aksiyon": "Hereket & wezipeler",

        "start": (
            "👋 <b>Habar Gysgaldyjy</b>\n\n"
            "Okalmadyk toparlary we forum mowzuklaryny seniň üçin gysgaça düşündirýärin.\n\n"
            "📋  <b>Gysgaça mazmun</b> — okalmadyk toparlary sanawlaýar\n"
            "👆  Topar → (mowzuk) → režim saýla → gysgaça mazmun\n"
            "✅  <b>Okaldy belle</b> bilen arassala\n\n"
            "Režimler: 📝 Umumy · 💡 Bilim & maslahat · 🎯 Hereket\n\n"
            "Aşakdaky düwmä ýa-da /ozet buýrugyna bas."
        ),

        "scanning_groups": "🔎 Toparlar barlanýar…",
        "scanning_topics": "🔎 Mowzuklar barlanýar…",
        "fetching_msgs": "📥 Habarlar alynýar…",
        "no_unread_groups": "✅ Okalmadyk habarly topar ýok. 🎉",
        "groups_header": (
            "📋 <b>Okalmadyk Toparlar</b>\n"
            "<i>Haýsysyny gysgaltaýyn?</i>\n"
            "<i>🗂 mowzukly topar · 💬 adaty topar</i>"
        ),
        "group_not_found": "Topar tapylmady.",
        "topic_not_found": "Mowzuk tapylmady.",
        "no_text_unread": "ℹ️ Tekstli okalmadyk habar tapylmady.",
        "pick_action": "📋 <b>{baslik}</b>\n<i>Näme edeýin?</i>",
        "no_unread_topics": "✅ <b>{name}</b> içinde okalmadyk mowzuk ýok.",
        "topic_pick_header": "🗂 <b>{name}</b>\n<i>Haýsy mowzugy gysgaltaýyn?</i>",
        "topic_btn": "💬 {title}  ·  {n}",

        "session_expired": "⌛ Bu gysgaltma sessiýasy indi hereketsiz. /ozet bilen täzeden başla.",
        "summarizing": "🤖 Gysgaldylýar… ({emoji} {ad})",
        "model_busy": "⚠️ Model häzir gysga. Biraz soňra gaýtadan synanyş.",
        "summarize_failed": "⚠️ Gysgaldyp bolmady: {hata}",
        "mode_empty": (
            "📋 <b>{baslik}</b>\n\n"
            "ℹ️ <i>Bu režimde ({emoji} {ad}) ähmiýetli zat ýok.</i>\n"
            "Başga režimde synanyşmak isleýärsiňmi?"
        ),
        "counter_full": "\n\n━━━━━━━━━\n📊 {sayi} tekst habary · {emoji} {ad} · jemi {toplam} okalmadyk",
        "counter_simple": "\n\n━━━━━━━━━\n📊 {sayi} tekst habary · {emoji} {ad}",

        "marked_read": "\n\n✅ <b>Okaldy diýip bellenildi.</b>",
        "mark_read_failed": "\n\n⚠️ Okaldy bellenip bolmady: {hata}",
        "closed": "❌ Ýapyldy.",
        "not_your_bot": "Bu bot seniňki däl.",

        "qa_detect_owner": "🔎 Topar eýesi anyklanýar…",
        "qa_owner_not_found": (
            "⚠️ Topar eýesi (döredijisi) anyklanyp bilinmedi. "
            "Bu topar üçin sorag-jogap çykaryp bilmeýärin."
        ),
        "qa_scan_owner": "📥 Topar eýesiniň habarlary barlanýar…",
        "qa_owner_no_unread": "ℹ️ Topar eýesiniň okalmadyk habary ýok.",
        "qa_downloading_images": "🖼 Suratlar göçürilýär…",
        "qa_preparing_file": "📝 Faýl taýýarlanýar…",
        "qa_sending_file": "📤 Faýl ugradylýar…",
        "qa_send_failed": "⚠️ Faýl ugradyp bolmady: {hata}",
        "qa_caption": "📄 {baslik} — {cift} sorag-jogap, {sayi} habar",
        "qa_ready": (
            "✅ <b>Sorag-jogap faýly taýýar</b>\n"
            "📄 {cift} sorag-jogap jübüti · 🖼 {resim} surat\n"
            "<i>Suratlary görmek üçin kompýuteriňde şu bukjany aç:</i>\n"
            "<code>{yol}</code>"
        ),
        "qa_md_title": "# Sorag-jogap — {baslik}",
        "qa_md_meta": "_{tarih} · {sayi} jogap_",
        "qa_md_question": "### ❓ {ad}",
        "qa_md_answer": "**💬 Jogap:**",
        "qa_md_unanswered": "## Jogapsyz habarlar",
        "qa_md_no_content": "(mazmun ýok)",

        "auto_header": (
            "⏰ <b>Awtomatik Gündelik Mazmun</b>\n"
            "Ýagdaý: {durum} · Her ertir 09:00\n"
            "Saýlanan: {g} topar + {k} mowzuk\n\n"
            "<i>💬 adaty topar: bas = saýla · 🗂 forum: bas = mowzuklara gir</i>"
        ),
        "auto_on": "🟢 açyk",
        "auto_off": "🔴 ýapyk",
        "auto_toggle_on": "🟢 Awtomatik: AÇYK (ýap)",
        "auto_toggle_off": "🔴 Awtomatik: ÝAPYK (aç)",
        "auto_forum_entry": "🗂 {name}  ▶︎",
        "auto_topics_count": "  ({n} mowzuk saýlandy)",
        "auto_topic_header": "🗂 <b>{name}</b>\n<i>Mazmuna goşmak isleýän mowzuklaryňy saýla.</i>",

        "bulletin_no_msgs": "📰 <b>{baslik}</b>\n\nℹ️ Soňky 24 sagatda habar ýok.",
        "bulletin_failed": "📰 <b>{baslik}</b>\n\n⚠️ Gysgaldyp bolmady: {hata}",
        "no_groups_selected": "ℹ️ Mazmun üçin hiç topar/mowzuk saýlanmady. /otomatik bilen saýla.",
        "test_running": "🧪 Synag mazmuny işledilýär… (biraz wagt alyp biler)",
        "test_done": "✅ Synag mazmuny tamamlandy.",

        "status": (
            "🤖 <b>Bot Ýagdaýy</b>\n\n"
            "⏱ Işleýän wagty: {sure}\n"
            "⏰ Awtomatik: {durum} (her ertir 09:00)\n"
            "📌 Saýlanan: {g} topar + {k} mowzuk\n"
            "📰 Soňky mazmun: {son}\n"
            "🌍 Dil: {lang}\n"
            "🧠 Model: {model}"
        ),
        "last_never": "entek işlemedi",
        "dur_days": "{n} gün",
        "dur_hours": "{n} sagat",
        "dur_minutes": "{n} minut",

        "lang_header": "🌍 <b>Dil</b>\nInterfeýs we mazmun dilini saýla:",
        "lang_changed": "✅ Dil <b>{lang}</b> edip bellenildi.",

        "cmd_ozet": "📋 Okalmadyk toparlary gysgalt",
        "cmd_otomatik": "⏰ Awtomatik gündelik mazmun sazlamalary",
        "cmd_dil": "🌍 Dili üýtget",
        "cmd_durum": "🤖 Bot ýagdaýy",
        "cmd_start": "👋 Başla / kömek",
    },
}
