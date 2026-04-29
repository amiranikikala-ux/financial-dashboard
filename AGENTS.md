# Financial Dashboard — Agent Instructions

> **3 ფაილი მართავს მუშაობას:** `CONTEXT_HANDOFF.md` (ცოცხალი state) · `docs/MASTER_PLAN.md` (roadmap) · ეს ფაილი (rules).

## სესიის დაწყება

1. წაიკითხე `CONTEXT_HANDOFF.md` — ახლა სად ვართ
2. წაიკითხე `docs/MASTER_PLAN.md` — რა სექციაში და რა Sprint Step-ში ვართ
3. წაიკითხე ეს ფაილი — როგორ ვმუშაობთ
4. ისტორიული evidence (commit X-ის დეტალი) → `HANDOFF.md` (index) → `HANDOFF_ARCHIVE/`
5. ენა: მომხმარებელთან **ქართული**, კოდი + commit message **ინგლისური**

## Stack

- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler · `server.py` (`:8000`)
- **Frontend**: React + Vite · `rs-dashboard/` (`:5173` dev)
- **Pipeline**: Excel/CSV → `generate_dashboard_data.py` → `data.json` → `/api/data`
- **AI**: Anthropic SDK + tool-use (29 tools) + Sonnet 4.6 default (Opus available)

## სამუშაო წესები

- `CONTEXT_HANDOFF.md` განაახლე **ყოველი session-ის ბოლოს** ან context 60%-ზე მისვლისას
- `docs/MASTER_PLAN.md` განაახლე მხოლოდ **სექციის Step 6 (User review) დახურვაზე** — სტატუსის სვეტი 🟢, deliverable SHA
- `HANDOFF.md` განაახლე მხოლოდ მაშინ, როცა archive-ში რამე გადადის (commit SHA → archive pointer)
- ტესტები არ წაშალო/შეასუსტო user-ის ცხადი მითითების გარეშე
- Build/test ვერიფიკაცია გააკეთე მხოლოდ შესაბამისი ცვლილების შემდეგ
- ახალი task-ის დაწყებამდე ნუ კითხულობ ზედმეტ ფაილებს
- **Surgical edits** — ყოველი ცვლილებული ხაზი task-ს უკავშირდება. სტილი/ფორმატირება/„უკეთესად დავწერდი" — არ შეეხო
- **Task-გარე bug** — შემთხვევით ნახო რეალური შეცდომა task-ს გარეთ → ცალკე აცნობე user-ს, იკითხე „გავასწორო ახლავე თუ ცალკე?". ნუ გაასწორებ ჩუმად იმავე commit-ში

## Proof gate (consolidated — Source-first principle)

ციფრი/feature „დასრულებული"-ა მხოლოდ მას შემდეგ, რაც **3-ფენიანი checklist** სრულდება:

1. **რა შემოწმდა source-თან 1:1** — Excel/CSV/JSON-დან ამოღებული ფინანსურ/გაყიდვების/მარჟის/მაღაზიის/პროდუქტის ციფრს უნდა ჰქონდეს: წყაროს row count + sum, ფორმულა, output sum, diff, **5+ representative spot-checks**. Source canonical (pipeline view): `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\` — 15 JSON config + `შემოტანილი პროდუქცია\` real folder + 5 symlink folders → parent's `Financial_Analysis\` (full structure: `CONTEXT_HANDOFF.md` §7). Diff = 0 ან source-level მიზეზით ახსნილი.
2. **რა derived-ია verified-დან** — derivation logic ცხადია, internal contradiction არ აქვს (e.g., KPI cells with mismatched scope = self-contradicting → fail).
3. **რა არ შემოწმდა** — ცარიელი slot-ის სიტყვით: „უცნობი" / „მონაცემი აკლია" / „candidate ვერ ამოვიღეთ". არასოდეს silent gap.

**Breakdown rule**: aggregate proof ≠ breakdown proof. UI-ში per-store / per-month / per-product breakdown → ყოველი ცალკე უნდა შემოწმდეს. ცრუ-ცარიელი 0 ₾ საეჭვოა — წყაროს ცადე, არ ჩაითვალოს „რეალური ნული".

**Inherited-code audit**: უკვე-არსებულ helper-ებს (resolver, parser, mapping, normalizer) არ ვენდე — spot-check რეალურ წყაროზე ვიდრე proof დავხურო. „ფუნქცია ადრე არსებობდა, სავარაუდოდ მუშაობს" = ცრუ ვარაუდი.

**ვერ დამტკიცდი** → დაწერე: „გაკეთებულია, მაგრამ ბოლომდე დამტკიცებული არ არის" + ცხადი open gap-ების სია. ცრუ „end-to-end PROOFED" აკრძალულია.

## მომხმარებელთან საუბრის ენა (CRITICAL)

- მომხმარებელი **არ არის პროგრამისტი** — plain ქართული, არასდროს technical jargon ახსნის გარეშე
- ფაილის/ფუნქციის სახელი ახსენე მხოლოდ მაშინ, როცა user თვითონ იხსენიებს
- ყოველი feature ახსენი **სამ ფენაში**: რას აკეთებს + რატომ გჭირდება + შედეგი რა იქნება
- ცხრილი / bullet / emoji — თვალსაჩინოდ
- კოდის block გამოიყენე მხოლოდ: (ა) user-მა თვითონ იხსენია, (ბ) business value ცხადი diff-ია
- გაგზავნამდე ყოველ ქართულ სიტყვას ცალ-ცალკე გადავიხედო — **სრული, ცნობილი, ნამდვილი** ქართული თუა (filler-words / partial tokens / English glue აკრძალულია)
- გაგზავნის წინ თავი ჰკითხე: „თუ user პროგრამისტი არ იყო, გასაგები იქნებოდა?"

## Session Pacing

- **Context size — 1M tokens (Opus 4.7, verified 2026-04-30 via WebSearch + official docs)**. 60% ceiling (600K tokens) გრძელ workflow-ში იშვიათად reach-ვდება — context space არ არის ძირითადი regression trigger.
- **Real regression trigger — output pattern detection** (size-independent): filler tokens (e.g., „ცადო" 3+ in single response), partial Latin tokens („magram", „magari"), self-correction loops, post-complex-tool-output degradation. Pattern detected → handoff offer.
- **Mitigation BEFORE restart** (per memory `feedback_session_discipline.md` row 19 — „ცალკე უნდა მოვაგვარო, არა სესიის შეჩერებით"): (a) smaller response, less parallel complexity; (b) avoid mixing Georgian + English + file-paths in one paragraph; (c) short cool-down — minimal-content reply, let pattern decay; (d) restart only if mitigation fails.
- **Why regression happens** (4 verified causes, size-independent): (1) **output distribution drift** — ქართული პასუხი ინგლისურ/technical content-ს მიჰყვება → token distribution shifts; (2) **token salience** — recently-used token returns as filler; (3) **mixed-language tool output background** — large non-Georgian blob affects subsequent Georgian generation; (4) **self-attention pattern lock** — one partial-token error fixates, similar errors compound.
- Scope creep = bug. „ოჰ, ესეც გავაკეთო" → ჯერ ვიკითხო user-ს.

## Correction Escalation

- User-მა **იგივე შეცდომა** 2-ჯერ გამისწორა ერთ session-ში → **restart** (`/restart-session` skill). Context დაბინძურდა, fix-ების კასკადი აღარ მუშაობს.
- 3-ჯერ იგივე შეცდომა **არასოდეს** — restart 2-ზე.
- **🚨 Cross-session pattern** (2026-04-29): partial Georgian tokens / filler-words / English-glue (e.g., „magram", „magari", „და-ცა") — ეს კონკრეტული შეცდომა **3 session-ზე** გამოვლინდა. მე-4 cross-session occurrence = **სასწრაფო restart**, არ ველოდები იმავე-session 2-rule-ს.
- restart = ახალი ჩატი + `CONTEXT_HANDOFF.md`-ის ცოცხალი წაკითხვა + user-ის ბოლო ცხადი მოთხოვნის განმეორება

## GitNexus (scoped — function edits only)

- **MUST** run `gitnexus_impact` ვიდრე shared/load-bearing function/class/method-ს ცვლი — სხვა callers-ის blast radius
- **EXEMPT**: JSON mapping update, docs ცვლილება, constant change, isolated frontend tweak
- HIGH/CRITICAL risk warning → user-ს ვუთხრა ვიდრე გავაგრძელო
- შესწორებამდე exploration: `gitnexus_query({query})` / `gitnexus_context({name})` (გრეპი-ს ცვლი)
- **Refactor (rename/extract)**: `gitnexus_rename({dry_run: true})` ჯერ; მერე `dry_run: false`
- Tools quick-reference + risk-level table + index-freshness ბრძანებები → `CLAUDE.md` GitNexus block. ⚠️ `CLAUDE.md`-ის strict „MUST run for ANY symbol" ფრაზებს ნუ აიღებ verbatim — ამ ფაილის scope-ი (shared function only) ვრცელდება

## Prompt Hygiene (SYSTEM_PROMPT_KA edits only)

- ruthlessly prune — დუბლიკატი section-ი წავშალო, verbose narrative → table or 2-line rule
- ყოველი rule-ს უნდა ჰქონდეს grep-assertion `tests/test_ai_prompts_phase*.py`-ში — სხვაგვარად refactor-ის დროს silently ქრება
- ახალი წესის დამატებამდე — ხომ არ ვრცელდება უკვე არსებულ წესით?

## Project Rules (current values)

- **Excel Georgian path**: `tools.py::_resolve_safe_path` uses `Path.absolute()`, NOT `Path.resolve()`
- **Supplier-product JOIN**: barcode/code only (1:1, exactly-one-row); name-fuzzy auto-match FORBIDDEN (Borjomi glass ≠ plastic). Exception: unique normalized name in PROTECTED retail category (cigarettes/alcohol per `SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS`)
- **retail_sales revenue**: `unit_price × quantity` per row. Pinned `tests/test_retail_sales_revenue_formula.py`
- **Destination resolver**: `rs_location_priority_order` keyword scan. New variants → `object_mapping.json:rs_location_to_object` + `tests/test_supplier_data_invariants.py`
- **ChromaDB 1.5.x `$lt`/`$gt`** don't work on string metadata — Python post-fetch filter mandatory
- **`.claude/scheduled_tasks.lock`** gitignored (Claude Code ScheduleWakeup artifact, machine-specific)
