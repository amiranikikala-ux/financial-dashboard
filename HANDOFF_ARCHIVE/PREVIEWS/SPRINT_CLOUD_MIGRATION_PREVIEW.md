# SPRINT — Cloud Migration (24/7 availability)

> **Status**: PREVIEW · NO CODE CHANGE
> **Date**: 2026-05-07
> **Owner ask**: dashboard + AI ხელმისაწვდომი იყოს მაშინაც, როცა მფლობელის კომპიუტერი გათიშულია. Telegram bot-ი ყოველთვის უპასუხოს. Megaplus მონაცემები ავტომატურად განახლდეს მაღაზიის სალარო-კომპიუტერიდან.
> **Trigger**: 2026-05-07 conversation — owner asked "კომპიუტერის გათიშვის შემთხვევაში როგორ შევინარჩუნოთ" → cloud server.

---

## TL;DR

ყველაფერი (backend + frontend + Telegram bot + AI + scheduler) გადადის Linux VPS-ზე (recommended: DigitalOcean, $18-24/თვე). მაღაზიის სალარო-კომპიუტერზე იდგმება პატარა Windows uploader, რომელიც დღიურ Megaplus zip-ფაილს თვითონ აგზავნის სერვერზე. Excel ფაილებისთვის (ბანკი, ხელფასი, ფაქტურა) dashboard-ზე ემატება „📎 ატვირთე" UI. **3 კრიტიკული გარე-ფაქტორი ჯერ არ არის ვერიფიცირებული** — rs.ge / TBC / BOG API-ების geo-restriction. ეს უნდა გადამოწმდეს IMPLEMENTATION-ის წინ. სრული გეგმა 4 sprint-ად იშლება (ერთ session-ში არ ეტევა).

---

## Inventory — რა წავიკითხე და რა ვიპოვე

### Components currently running locally

| კომპონენტი | ფაილი | ახლა როგორ მუშაობს | Cloud equivalent |
|---|---|---|---|
| Backend API | `server.py` | Windows service (NSSM) `FinancialDashboardBackend` :8000 | systemd service Linux-ზე |
| Pipeline | `generate_dashboard_data.py` | APScheduler-ი server-ში 60-წუთიანი interval-ით | იგივე — APScheduler უცვლელი |
| Frontend | `rs-dashboard/dist/` | Built static, served by FastAPI | იგივე — `StaticFiles` mount |
| Telegram bot | `telegram_bot.py` | ცალკე process, ხელით ეშვება | systemd service (ცალკე unit) |
| AI Advisor | `dashboard_pipeline/ai/` | Anthropic SDK + chromadb + sentence-transformers | იგივე — ყველა Python-ია |
| Forecasting | `dashboard_pipeline/ai/forecasting.py` | Prophet + statsmodels | იგივე |
| Memory | `ai_vectors/` | chromadb local | იგივე — local files (volume mount) |

### Data inventory (folder sizes)

| Folder | Size | Cloud strategy |
|---|---|---|
| `Financial_Analysis/მეგაპლიუსის არქიტექტურა/` | **1.2 GB** | One-time bulk transfer + daily delta zip-ით |
| `Financial_Analysis/შემოტანილი პროდუქცია/` | 82 MB | One-time transfer; rare updates |
| `Financial_Analysis/cache/` | 35 MB | Regenerated server-ზე — არ გადავიტანოთ |
| `Financial_Analysis/ბოგ ბანკი ამონაწერი/` | 25 MB | One-time + Excel upload UI |
| `Financial_Analysis/თბს ბანკი ამონაწერი/` | 8.1 MB | იგივე |
| `Financial_Analysis/რს ზედნადები/` | 8.1 MB | API-დან regen-ვდება, არ გადავიტანოთ |
| Configuration JSONs (15+ files) | <100 KB | One-time + git-tracked |

**Total bulk transfer estimate: ~1.4 GB** (one-time, შეიძლება ZIP-ად დაიდოს და SCP-ით). შემდეგ daily delta = რამდენიმე MB.

### Megaplus daily zip pattern (verified)

`PLUS_1329_MEGA_YYYYMMDD.zip` — ერთი per day per shop. ნიმუში: `Financial_Analysis/მეგაპლიუსის არქიტექტურა/დვაბზუ/PLUS_1329_MEGA_20260505.zip`. 8 დღის ფაილი ერთ ფოლდერში → **დღიური delta = ერთი ZIP (~რამდენიმე MB).** Cloud uploader = მცირე payload.

### Authentication state (current)

`server.py:46-69` — `ApiKeyMiddleware`. `DASHBOARD_API_KEY` environment variable-ი თუ მითითებულია, `X-API-Key` header სავალდებულოა. ეს header-based auth — **public-internet-ის ღირსი არ არის** (no rate-limit per user, no session, no UI login). Cloud-ზე გადასვლისას proper auth აუცილებელია.

### Network endpoints used (need geo-restriction verification)

| API | Used by | Geo-blocked? |
|---|---|---|
| **rs.ge SOAP** (`eapi.rs.ge`) | waybills, invoices | ⚠️ UNKNOWN — ხშირად Georgian IP-ის მოლოდინი |
| **TBC API** (`api.tbcbank.ge`) | bank statements | ⚠️ UNKNOWN |
| **BOG API** (`api.businessonline.ge`) | bank statements | ⚠️ UNKNOWN |
| **Anthropic API** (`api.anthropic.com`) | AI Advisor | ✅ Global |
| **Telegram API** (`api.telegram.org`) | bot | ✅ Global |

**Memory note**: `project_rsge_soap_api.md` documents auth + endpoints, **არ არის** explicit geo-restriction confirmation. **MUST VERIFY** Sprint 1-ში.

---

## Risks / pitfalls

| # | რისკი | Severity | Mitigation |
|---|---|---|---|
| **1** | rs.ge / TBC / BOG API შეიძლება Georgian IP-ის მოლოდინი ჰქონდეს. Cloud server EU/US-ში → API ფეილავს | **CRITICAL** | Sprint 1 გადამოწმებად. თუ blocked: (ა) VPN tunnel მფლობელის ქართულ ინტერნეტამდე; (ბ) ქართულად მდებარე VPS (data-service.ge / proservice.ge); (გ) hybrid — local proxy ქართულ კომპიუტერზე API ზარებს უგზავნის cloud-ს |
| **2** | Megaplus ბულკ თრანსფერი (1.2 GB) ნელი ინტერნეტით | MED | One-time. SCP/rsync. ან ZIP-ად. ერთ ღამეში დასრულდება. |
| **3** | chromadb + sentence-transformers + Prophet RAM-ი მოითხოვენ ~2-4 GB | MED | DigitalOcean $24/თვე droplet (4GB RAM) — საჭიროა, არა cheapest. |
| **4** | Pipeline regen ~17 წუთი — heavy CPU | MED | 2 vCPU minimum. შეიძლება ცარიელ შპერიოდად განრიგდეს (ღამე 03:00). |
| **5** | Authentication missing — proper login UI | HIGH | Sprint 4. ცალცალკე session. რეკომენდაცია — single-user password + session cookie. ან Cloudflare Access (free tier) იყენოთ. |
| **6** | Excel upload UI — ფაილის size limit, MIME type, virus | MED | FastAPI `UploadFile` + size cap 50MB + extension whitelist + atomic write |
| **7** | Megaplus uploader — store computer წვდომა | MED | მფლობელი მაღაზიაში მიდის და ახდენს დაყენებას ერთხელ. შემდეგ თვითონ. |
| **8** | Backup strategy — სერვერი ფეილ-როდი → მონაცემები კარგდება | HIGH | DigitalOcean snapshot ($1/თვე) + ლოკალური git mirror configs-ისთვის |
| **9** | HTTPS / domain | LOW | Caddy reverse proxy + Let's Encrypt automatic. domain-ი ~30 ლარი/year. |
| **10** | Data privacy — სხვისი ბიზნეს მონაცემი cloud-ში | LOW (decision) | Owner-მა უნდა დაადასტუროს. EU server (DigitalOcean Frankfurt) GDPR-უსაფრთხოა. |

---

## Scope recommendation — split into 4 sprints

ეს ერთ session-ში **შეუძლებელია**. რეკომენდირებული გაყოფა:

### Sprint 1 — Verification & Provider Setup (1 session)
- ⚠️ **Blocking verification**: rs.ge / TBC / BOG API geo-restriction ცდა (cloud სერვერიდან curl/Python ცდა)
- Provider შერჩევა (DigitalOcean default, Hetzner alternative)
- Domain registration (`rsdash.ge` ან `dashboard.{owner-business}.ge`)
- Basic Linux VPS provisioning + SSH access
- **Deliverable**: ცარიელი ღრუბელის სერვერი, domain → IP, geo-restriction risk მოგვარებული ან ცხადი ალტერნატიული გეგმა

### Sprint 2 — First Deployment (1-2 sessions)
- Python dependencies install (Linux compat)
- Code transfer (git clone + data bulk upload)
- systemd services (backend + telegram bot + scheduler)
- Caddy reverse proxy + HTTPS
- Smoke test: dashboard ხელმისაწვდომია domain-ზე
- **Deliverable**: ცოცხალი dashboard ღრუბელში, ფუნქციონალი იგივე, რაც ლოკალურად

### Sprint 3 — Megaplus Uploader + Excel Upload UI (1 session)
- მაღაზიის Windows uploader — small Python script + Task Scheduler entry
- Backend upload endpoint (`POST /api/megaplus/upload`)
- Frontend upload UI (Excel-ისთვის)
- Backend `/api/files/upload` endpoint
- **Deliverable**: ფაილების ავტო-სინქი + ხელით ატვირთვა მუშაობს

### Sprint 4 — Authentication + Hardening (1 session)
- Login UI (single-user password)
- Session cookie + HMAC
- Rate limiting per user
- Cloudflare Access (alternative — much simpler)
- Backup automation (daily DO snapshot)
- **Deliverable**: production-ready სისტემა

**Total estimate**: 4-6 sessions. Owner-ი ჩვენთან თანამშრომლობს მხოლოდ Sprint 1-ში (provider account, payment) და Sprint 3-ში (მაღაზიაში uploader-ის დაყენება).

---

## Files expected to change

### Sprint 1 (verification + provider)
- ❌ NO project file changes. ცხრილში ცნობების შეგროვება, provider account creation.
- ✅ `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_1_CLOUD_VERIFY_RESULTS.md` (NEW) — verification results

### Sprint 2 (deployment)
- ✅ `deploy/` folder (NEW):
  - `deploy/systemd/financial-dashboard.service`
  - `deploy/systemd/telegram-bot.service`
  - `deploy/Caddyfile`
  - `deploy/setup.sh` (one-shot Linux setup)
  - `deploy/README.md`
- ✅ `requirements.txt` — verify all deps Linux-compat (most are)
- ✅ `.env.example` — environment variable template
- ❌ `server.py` — minor: handle `/data.json` path on Linux
- ❌ `backend_paths.py` — Linux path support

### Sprint 3 (uploader + UI)
- ✅ `tools/megaplus_uploader.py` (NEW) — Windows daemon
- ✅ `tools/megaplus_uploader_install.bat` (NEW) — Task Scheduler installer
- ✅ `server.py` — new endpoints: `POST /api/megaplus/upload`, `POST /api/files/upload`
- ✅ `rs-dashboard/src/FileUpload.jsx` (NEW) — upload modal
- ✅ `dashboard_pipeline/file_intake.py` (NEW) — atomic file write + validation

### Sprint 4 (auth)
- ✅ `dashboard_pipeline/auth.py` (NEW) — session management
- ✅ `server.py` — replace `ApiKeyMiddleware` with session-based auth
- ✅ `rs-dashboard/src/Login.jsx` (NEW)
- ✅ `rs-dashboard/src/App.jsx` — auth gate

---

## Test plan

ცდები — Sprint-ის ბოლოს, არა preview-ში. სავარაუდო:

| Sprint | New tests |
|---|---|
| 1 | `tests/test_geo_verification.py` — curl-based smoke (skipped if no creds) |
| 2 | `tests/test_deploy_paths_linux.py` — path resolution რეგრესია |
| 3 | `tests/test_file_upload_api.py` — atomic write, size cap, extension whitelist |
| 3 | `tests/test_megaplus_uploader.py` — delta detection logic |
| 4 | `tests/test_auth_session.py` — login, session cookie, expiry |

---

## Cost estimate (monthly)

| რა | სად | ფასი |
|---|---|---|
| VPS (4GB RAM, 2 vCPU, 80GB SSD) | DigitalOcean (Frankfurt) | $24 (~65 ₾) |
| Snapshot backup | DigitalOcean | $1.20 (~3 ₾) |
| Domain | namecheap / .ge registrar | ~30 ₾/year (~2.5 ₾/თვე) |
| Anthropic API | Anthropic (already paying) | unchanged |
| Cloudflare (optional, auth+CDN) | Cloudflare | $0 (free tier sufficient) |
| **სულ** | | **~70 ₾/თვე** |

ალტერნატივა — ქართული VPS provider (geo-restriction-ის რისკის mitigation): proservice.ge, datacomm.ge — ფასი ~80-150 ₾/თვე, მაგრამ Georgian IP გარანტირებული.

---

## Self-check checklist (pre-implementation)

- [ ] Owner-მა დაადასტურა cloud-migration goal (vs. dedicated mini-PC)
- [ ] Owner-მა აირჩია provider preference (DigitalOcean vs ქართული)
- [ ] Owner-მა აირჩია domain name
- [ ] Sprint 1 verification შესრულდა (geo-restriction)
- [ ] Backup plan ცხადია (snapshot + git)
- [ ] Owner-ი თანახმა cost-ზე (~70 ₾/თვე)

---

## Open questions for owner

1. **Provider**: DigitalOcean (EU) — იაფი + ცნობილი. ქართული VPS — IP გარანტირებული, ცოტა ძვირი. რომელი?
2. **Domain**: `rsdash.ge`-სტილის ცალკე name? თუ subdomain არსებულ business website-ზე?
3. **Authentication**: Cloudflare Access (1-კლიკიანი, free) თუ custom login UI?
4. **Excel upload**: ვინ ატვირთავს — მფლობელი თვითონ, თუ ბუღალტერსაც ჰქონდეს წვდომა?
5. **Megaplus store PC**: მაღაზიაში სალარო-კომპიუტერზე SSH/Remote-ი ხელმისაწვდომია? ფიზიკური ვიზიტი საჭიროა Sprint 3-ში uploader დასაყენებლად?

---

## Evidence sources

- `CONTEXT_HANDOFF.md` (2026-05-07 state)
- `server.py` lines 1-100 (FastAPI + middleware + scheduler)
- `telegram_bot.py` lines 1-80 (long-poll setup)
- `requirements.txt` (full dependency list)
- `Financial_Analysis/` folder size inventory (`du -sh`)
- `Financial_Analysis/მეგაპლიუსის არქიტექტურა/დვაბზუ/` — verified daily ZIP pattern
- Memory: `project_rsge_soap_api.md`, `project_bog_two_accounts.md`, `feedback_single_url_workflow.md`
