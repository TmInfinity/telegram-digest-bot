# Telegram Özet & Bülten Botu

Kişisel, tek kullanıcılı bir Telegram mesaj özetleme sistemi. Okunmamış grupları
ve forum konularını yapay zekâ ile özetler; istersen her sabah otomatik bülten gönderir.

## Nasıl çalışır?

İki kimlik birlikte çalışır:

- **Telethon (userbot)** — senin kendi hesabın, mesajları *okur* (botlar grup geçmişi
  okuyamadığı için userbot şart).
- **python-telegram-bot** — ayrı bir BotFather botu, seninle *konuşur* (komut/buton).
- **OpenRouter** — özetlemeyi yapan yapay zekâ (model `.env`'den seçilir, varsayılan
  DeepSeek V3).

## Komutlar

| Komut | İş |
|---|---|
| `/ozet` | Okunmamış grupları listeler → grup/konu → mod seç → özet |
| `/otomatik` | Otomatik günlük bülten için grup/konu seçimi ve aç/kapa |
| `/durum` | Bot durumu (çalışma süresi, seçili gruplar, aktif model) |
| `/start` | Karşılama / yardım |

Özet modları: 📝 Genel · 💡 Bilgi & ipucu · 🎯 Aksiyon & görevler.
Ayrıca `/ozet` içinden **📄 Soru-Cevap dosyası** çıkarılabilir (resimler dahil `.md`).

## Kurulum

1. `.env` dosyası oluştur (chmod 600):
   ```
   TG_API_ID=...
   TG_API_HASH=...
   TG_BOT_TOKEN=...
   TG_CHAT_ID=...
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324   # isteğe bağlı
   ```
   - `TG_API_ID` / `TG_API_HASH`: https://my.telegram.org
   - `TG_BOT_TOKEN`: BotFather'dan. `TG_CHAT_ID`: `uv run python chatid_bul.py` ile bul.
   - `OPENROUTER_API_KEY`: https://openrouter.ai/keys
2. Çalıştır: `uv run python bot.py`
3. (macOS) Arka planda 7/24 için `launchd` ile servisleştirilir.

## Notlar

- İlk çalıştırmada Telethon telefon + kod ile giriş yapıp `ozet_session.session`
  dosyasını oluşturur. **Bu dosya hesabının tam erişimidir — asla paylaşma/commit etme.**
- Sırlar (`.env`, `*.session`, `ayarlar.json`, loglar) `.gitignore`'dadır.
- Daha fazla mimari/karar detayı için `CLAUDE.md`'ye bak.
