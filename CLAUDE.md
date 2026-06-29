# CLAUDE.md — Telegram Özet & Bülten Botu

Bu dosya, Claude Code'un bu projede çalışırken bağlamı anlaması içindir.
**Yanıtlar ve açıklamalar Türkçe olmalı.** Kullanıcı (Maksat) Türkçe konuşur.

---

## Proje nedir?

Telethon (userbot) + python-telegram-bot (bot arayüzü) + Google Gemini (özetleme)
kullanan, kişisel bir Telegram mesaj özetleme sistemi. Tek kullanıcılıdır (sahibi
Maksat). macOS'ta `launchd` ile arka planda 7/24 (Mac açıkken) çalışır.

İki ana yetenek:
1. **Manuel özet** (`/ozet`): okunmamış grupları/forum konularını listeler, seçilen
   sohbeti 3 moddan biriyle özetler ya da soru-cevap dosyası çıkarır.
2. **Otomatik günlük bülten** (`/otomatik` + her sabah 09:00): seçili grup/konuların
   son 24 saatini bilgi-odaklı bültenle özetleyip bota gönderir, sonra okundu yapar.

---

## Mimari ve kritik kararlar

- **İki kimlik birlikte çalışır:** Telethon = kullanıcının kendi hesabı, mesajları
  OKUR (botlar DM/grup geçmişi okuyamadığı için userbot şart). python-telegram-bot =
  ayrı bir BotFather botu, kullanıcıyla KONUŞUR (komut/buton/teslim). İkisi aynı
  asyncio event loop'unda çalışır; `tele` (Telethon) global, bot handler'ları içinde
  doğrudan `await tele...` çağrılır.
- **Okunmamış mantığı:** Telegram `read_inbox_max_id` tutar; bundan büyük ID'li
  mesajlar okunmamıştır. `iter_messages(min_id=read_inbox_max_id)` ile çekilir.
- **Forum grupları:** `dialog.entity.forum == True`. Grup seviyesindeki
  `unread_count` forumlarda GÜVENİLMEZ — bu yüzden `okunmamis_gruplari_getir()`
  forumlar için konu konu (`GetForumTopicsRequest`) gerçek okunmamışa bakar. Forum
  konu mesajları `iter_messages(reply_to=topic_id, ...)` ile çekilir.
- **GetForumTopicsRequest** `telethon.tl.functions.messages` altındadır (channels
  DEĞİL — Telegram taşıdı), parametre `peer=` (channel= değil).
- **Konu okundu yapma:** `ReadDiscussionRequest(peer, msg_id=topic_id, read_max_id=top_message)`.
  Normal grup okundu: `tele.send_read_acknowledge(entity)`.
- **Sadece sahip kullanabilir:** her handler `sadece_sahip()` / `SAHIP_ID` kontrolü yapar.

## Özetleme (OpenRouter)

- Sağlayıcı: **OpenRouter** (OpenAI-uyumlu HTTP API, `httpx` ile çağrılır). Model
  `.env`'deki `OPENROUTER_MODEL` ile değişir; varsayılan `deepseek/deepseek-chat-v3-0324`
  (ucuz, Türkçesi iyi, agresif içerik filtresi yok). Eskiden Google Gemini kullanılıyordu
  ama `gemini-2.5-flash` grup mesajlarını `PROHIBITED_CONTENT` ile sık sık blokluyordu;
  bu yüzden OpenRouter'a geçildi.
- `_ai_cagir()` ortak çağrı + 429/5xx/yoğunluk için 4 denemeli geri çekilme (retry).
  Boş yanıtı da hataya çevirir, sessizce `None` geçirmez. SENKRON+bloklayıcı olduğu
  için handler'lardan `asyncio.to_thread(_ai_cagir, ...)` ile çağrılır (yoksa Telethon
  dahil tüm olay döngüsü donar).
- NOT: OpenRouter ücretsiz (`:free`) modeller paylaşımlı havuzda olduğundan sık `429`
  yer; bu yüzden küçük kredi + ucuz ücretli slug tercih edildi.
- 3 özet modu: `genel`, `bilgi`, `aksiyon` (`MOD_PROMPTLARI`). bilgi/aksiyon boşsa
  "BOŞ" döndürür (`_bos_mu`), kullanıcıya diğer modlar önerilir.
- Otomatik bülten ayrı prompt: `BULTEN_PROMPT` — BİLGİ ODAKLI (görev listesi değil),
  uzun olabilir, sonunda `KRITIK: <id'ler>` satırıyla en kritik 1-2 mesajı işaretler
  (`_kritik_ayikla`), bunlara `t.me/c/...` "Git" butonu konur (`_msg_link`).

## Soru-Cevap dosyası modu

- `/ozet` → grup/konu seç → "📄 Soru-Cevap dosyası" butonu.
- Grup SAHİBİNİ (creator) bulur (`grup_sahibi_bul`, ChannelParticipantCreator).
- Sahibin okunmamış mesajlarını + yanıt verdiği soruları eşler (`_yanit_hedefi`).
- Her dışa aktarım kendi klasörüne: `soru_cevap/<grup>_<zaman>/` içine `.md` + `resimler/`.
  Resimler indirilir, markdown'a `![](resimler/x.jpg)` gömülür. Telegram'a `.md` belge
  olarak gönderilir; resimler Mac klasöründe görünür.

## Dosya/format konuları (dikkat)

- **Telegram mesajları HTML parse_mode ile gönderilir.** Dinamik metin MUTLAKA
  `html.escape()` ile kaçırılır (eskiden Markdown parse hatası yaşandı). Markdown
  KULLANMA; Gemini prompt'larında da "Markdown işareti kullanma" denir.
- **4096 karakter sınırı:** uzun mesajlar `_parcala()` ile bölünür (butonlar son parçada).
- `msg.text` Telethon'da resim altı yazıyı (caption) da içerir.

## Yapılandırma & kalıcılık

- `.env` (chmod 600, .gitignore'da): `TG_API_ID, TG_API_HASH, OPENROUTER_API_KEY,
  OPENROUTER_MODEL, TG_BOT_TOKEN, TG_CHAT_ID`. `python-dotenv` ile yüklenir.
  (`OPENROUTER_MODEL` zorunlu değil; yoksa kod varsayılan slug'a düşer.)
- `ayarlar.json`: `{otomatik_acik, gruplar:[id...], konular:[[grup_id,konu_id]...],
  son_bulten, son_bulten_tarih, son_mod}`. `son_bulten_tarih` (YYYY-MM-DD) günde tek
  bülten + uyku telafisi için; `son_mod` mod hafızası için.
- `ozet_session.session`: Telethon oturumu — HESABIN TAM ERİŞİMİ, asla paylaşma/commit etme.
- Loglar: `app.log` (RotatingFileHandler, tarih damgalı, 1MB×3 yedek). Eski
  `bot.log`/`bot.error.log` launchd çıktısıdır (çökme için).

## Komutlar

`/ozet`, `/otomatik`, `/durum`, `/test_bulten` (gizli, bülteni hemen çalıştırır), `/start`.

---

## Çalıştırma / geliştirme akışı

- Ortam: `uv` ile yönetilir (`pyproject.toml`, `.venv`). Çalıştırma: `uv run python bot.py`.
- Bağımlılık ekleme: `uv add <paket>`. Mevcutlar: telethon, httpx (OpenRouter
  çağrısı için), python-telegram-bot[job-queue], python-dotenv.
- **Bot launchd ile çalışır** (`~/Library/LaunchAgents/com.maksat.telegramozet.plist`).
  Kodu değiştirince servisi yeniden başlat:
  ```
  launchctl bootout gui/$(id -u)/com.maksat.telegramozet
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.maksat.telegramozet.plist
  launchctl list | grep telegramozet   # PID görünmeli, çalışıyor demek
  ```
  Not: bootout sonrası bootstrap'i hemen yaparsan "I/O error" gelebilir; 1-2 sn bekle.
- Elle test için terminalde `uv run python bot.py` da çalıştırılabilir AMA launchd
  kopyası açıkken aynı anda çalıştırma (token çakışır). Önce bootout yap.
- Söz dizimi kontrolü: `python3 -m py_compile bot.py`.

## Bilinen sınırlar / olası geliştirmeler

- `MAX_MESSAGES = 500`: çok yoğun gruplarda en eski okunmamışlar kaçar (sessizce).
- Otomatik bülten yalnız Mac açıkken çalışır. 09:00'da Mac uyuyorsa o tetik kaçar AMA
  artık TELAFİ var: `bulten_telafi_job` her 120 sn'de bir kontrol eder; Mac uyanınca
  (09:00 sonrası) bugünün bülteni çalışmadıysa hemen çalıştırır. Günde tek sefer
  garantisi `son_bulten_tarih` + `_bulten_lock` ile sağlanır. Mac gün boyu hiç
  uyanmazsa yine de o gün bülten gelmez.
- Görüntü analizi (Gemini'ye resim) YOK — bilinçli karar (kota/hız). Resimler sadece
  soru-cevap dosyasına ham gömülür.
- Önbellek (`ONBELLEK`) bellekte; bot yeniden başlayınca mod-seçim oturumları düşer
  (kullanıcıya "oturum geçersiz, /ozet ile tekrar başla" denir).

## Tarz / çalışma tercihleri (kullanıcı)

- Türkçe yanıt. Adım adım ilerle, her değişiklikten sonra test ettir.
- Açık öneri sun (seçenek yığını değil). Tek seferde tek büyük değişiklik yap.
- Güvenlik: sırları (.env, .session, token) asla loglama/commit etme. Kullanıcı
  bilgi güvenliği öğrencisi; güvenlik gerekçelerini açıklaman makbule geçer.
