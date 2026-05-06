# Farcaster Alpha Bot

Auto-post crypto alpha to your Farcaster account.
Source: list of crypto Twitter accounts you choose. Style: like [@aixbt_agent](https://x.com/aixbt_agent) — short, lowercase, observational, ticker-aware.

> **Persona**: lowercase, no hashtags, no emojis, references `$TICKER`s and concrete numbers. The LLM is instructed to never invent numbers and to return `SKIP` if the source has no real alpha.

---

## Cara kerja singkat

1. **GitHub Actions** trigger setiap jam (cron `17 * * * *`).
2. Bot ambil tweet terbaru dari list akun di `config/accounts.yml` (default: 24 jam terakhir).
3. Tweet yang belum pernah diposting di-filter, dipilih 1 yang paling fresh (random tiebreak top-3).
4. **OpenAI `gpt-4o-mini`** rewrite jadi single post a la aixbt_agent.
5. Hasilnya di-post ke Farcaster lewat **Neynar API**.
6. State (id tweet yang udah dipost) disimpan di `data/posted.json` dan di-commit balik ke repo.

Frekuensi posting dikontrol pakai 2 hal:
- **Active hours** (`ACTIVE_HOURS_START_UTC` & `_END_UTC`): di luar jam ini, tick di-skip total.
- **Probability gate** (`POST_PROBABILITY`): tiap tick di dalam active hours, post dengan probabilitas ini.

Default: cron 1×/jam, active hours 02:00–20:00 UTC (= 09:00–03:00 WIB), `POST_PROBABILITY=0.5` → rata-rata ~9 post/hari, distribusi random.

---

## Setup (sekali doang)

### 1. Clone & buat repo GitHub kamu sendiri

```bash
git clone <this-repo-url>
cd farcaster-alpha-bot
gh repo create my-farcaster-alpha-bot --private --source=. --push
```

### 2. Bikin Neynar account + signer

1. Sign up di https://neynar.com (free tier 1000 calls/day cukup banget).
2. Dashboard → **API Keys** → copy `API key` → simpan sebagai `NEYNAR_API_KEY`.
3. Dashboard → **Agents/Signers** → klik **Create Agent** (atau **Create Signer** bila kamu mau pakai akun Farcaster yg udah ada). Approve via Warpcast saat diminta.
4. Copy `signer_uuid` → simpan sebagai `NEYNAR_SIGNER_UUID`.

> Kalau pakai signer untuk akun Farcaster existing kamu, biaya storage 1× di-handle oleh kamu/Neynar; ikuti instruksi di dashboard.

### 3. OpenAI API key

1. https://platform.openai.com/api-keys → Create new secret key.
2. Default model: `gpt-4o-mini` (~$0.15/1M input, $0.60/1M output). Estimasi biaya: < $1/bulan untuk 10 post/hari.

### 4. Twitter source

Bot punya 3 source pluggable. Pilih salah satu:

#### a) `xcancel` (gratis, default — butuh whitelist sekali)

xcancel.com adalah Nitter mirror yg masih jalan. Mereka anti-scraping, jadi RSS feed harus di-whitelist:

1. Push repo dulu, commit kosong gak masalah.
2. Trigger workflow `post-cast` manual lewat tab **Actions** dengan `dry_run=true`. Logs akan menampilkan token whitelist (32+ hex chars) dari xcancel.
   - Atau jalankan `python -m src.main -vv --dry-run` lokal untuk dapat token-nya.
3. Email **`rss [AT] xcancel [DOT] com`** dengan token tsb dan minta whitelist (sekali doang).
4. Setelah whitelisted (biasanya beberapa jam), bot otomatis dapet feed beneran.

> Ini limitasi xcancel, bukan bot-nya. Kalau kamu pengen langsung jalan tanpa nunggu, pakai opsi `apify` di bawah.

#### b) `apify` (sangat reliable, $5/bulan free credits)

1. Sign up di https://apify.com → Settings → Integrations → API → copy token → simpan sebagai `APIFY_TOKEN`.
2. Set repo variable `TWITTER_SOURCE=apify`.
3. Default actor: `apidojo/tweet-scraper` (~$0.4/1k tweets). Free credits ($5) = ~12k tweets/bulan, jauh lebih dari cukup.

#### c) `fixture` (testing only)

Set `TWITTER_SOURCE=fixture` & edit `data/fixture_tweets.json`. Bot akan baca dari file tsb. Berguna buat dry-run testing.

### 5. Edit list akun

`config/accounts.yml` → tulis username-nya (tanpa `@`):

```yaml
accounts:
  - aixbt_agent
  - cobie
  - 0xMert_
  - DeFi_Dad
```

### 6. Set GitHub Actions secrets & variables

Di repo settings → **Secrets and variables** → **Actions**:

**Secrets** (sensitive):
| Name | Value |
| --- | --- |
| `NEYNAR_API_KEY` | dari step 2 |
| `NEYNAR_SIGNER_UUID` | dari step 2 |
| `OPENAI_API_KEY` | dari step 3 |
| `APIFY_TOKEN` | dari step 4b (kalau pakai apify) |

**Variables** (non-sensitive, optional — semua punya default):
| Name | Default | Description |
| --- | --- | --- |
| `TWITTER_SOURCE` | `xcancel` | `xcancel` / `apify` / `fixture` |
| `OPENAI_MODEL` | `gpt-4o-mini` | bisa diganti `gpt-4o` kalau mau hasil lebih bagus |
| `FARCASTER_CHANNEL_ID` | (kosong) | mis. `alpha`, `crypto` — kalau mau post ke channel tertentu |
| `POST_PROBABILITY` | `0.5` | 0.0-1.0, tinggiin kalo mau lebih sering posting |
| `ACTIVE_HOURS_START_UTC` | `2` | mulai jam segini UTC |
| `ACTIVE_HOURS_END_UTC` | `20` | berhenti jam segini UTC |
| `LOOKBACK_HOURS` | `24` | seberapa lama lookback tweets |
| `MIN_LENGTH` | `80` | output minimum char |
| `MAX_LENGTH` | `320` | output maximum char |

### 7. Jalankan!

- **Otomatis**: cron-nya udah aktif begitu workflow ter-commit. Tunggu sampai jam berikutnya.
- **Manual trigger**: GitHub Actions tab → workflow `post-cast` → **Run workflow** → pilih `force=true` & `dry_run=true` untuk test tanpa beneran post.
- **Local test**:
  ```bash
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env  # isi credentials
  python -m src.main -vv --dry-run --force --any-time   # test tanpa post
  python -m src.main -vv --force --any-time             # post beneran
  ```

---

## Mengontrol jumlah post per hari

Bot tidak punya counter "post N kali per hari". Jumlah post per hari emerge dari kombinasi:

- jumlah jam aktif × `POST_PROBABILITY`

Contoh: 18 jam aktif × 0.5 = 9 post/hari (rata-rata).

Mau **5 post/hari**: set `POST_PROBABILITY=0.28` (18 × 0.28 ≈ 5).
Mau **10 post/hari**: set `POST_PROBABILITY=0.55`.

Cron juga bisa diatur di `.github/workflows/post.yml` (`schedule.cron`):
- `*/30 * * * *` — tiap 30 menit (lebih granular)
- `0 */2 * * *` — tiap 2 jam (lebih hemat)

---

## Struktur kode

```
src/
├── main.py              # entrypoint: orchestrator + CLI args
├── config.py            # env + YAML loader
├── state.py             # data/posted.json read/write
├── llm_rewriter.py      # OpenAI gpt-4o-mini -> aixbt-style cast
├── farcaster_client.py  # Neynar publish_cast wrapper
└── sources/
    ├── base.py          # Tweet dataclass + TwitterSource ABC
    ├── xcancel_source.py # Nitter RSS via xcancel.com
    ├── apify_source.py  # Apify actor scraper
    └── fixture_source.py # local JSON for testing
```

---

## Customizing the persona

Edit `SYSTEM_PROMPT` di `src/llm_rewriter.py`. Kalau mau persona beda (mis. lebih galak, lebih cuan-bro, atau bilingual), tinggal ubah prompt-nya. Prompt sekarang:

- all lowercase, no hashtags, no emojis
- 1-4 short sentences, max 320 chars
- observational tone
- $TICKER references, real numbers only
- `SKIP` for non-alpha sources (memes, generic takes)

---

## Troubleshooting

**Bot post-nya jelek / mirip aslinya banget**
→ Naikin `POST_PROBABILITY` lebih rendah dan tighten prompt di `llm_rewriter.py`. Bisa juga ganti model ke `gpt-4o` (`OPENAI_MODEL=gpt-4o`).

**`No tweets fetched` di logs**
→ Kalau pakai `xcancel`, kemungkinan belum di-whitelist. Cek logs untuk token, email ke xcancel.

**Neynar error 403/401**
→ `NEYNAR_SIGNER_UUID` belum di-approve. Cek dashboard Neynar → Signers → status `pending_approval` vs `approved`.

**Tweet sama di-post 2×**
→ Pastikan workflow punya `permissions: contents: write` (udah default). State file `data/posted.json` harus di-commit balik tiap run.

**Mau pause dulu**
→ Disable workflow di GitHub Actions tab atau set `POST_PROBABILITY=0`.

---

## License

MIT.
