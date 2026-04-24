---
description: Evidence-only sprint preview — gathers scope/risks/tests/files BEFORE any code change. Writes one .md to HANDOFF_ARCHIVE/PREVIEWS/.
---

# /preview — Sprint scoping & evidence gathering

## როდის გააქტიურდეს

- User-მა გაასწავა ახალი sprint / feature / refactor
- მისცა topic: "/preview Sprint 3d tax_flow cross-bank cache" ან "/preview RS eApi integration"
- **Before any code.** თუ code უკვე დაწერილია — ეს არასწორი command-ია, გამოიყენე `/handoff` ან უბრალოდ implement-ი.

## Purpose

ერთი .md ფაილის დაწერა რომელიც შეიცავს ყველაფერს რაც შემდეგ session-ში იმპლემენტაციისთვის საჭიროა — არა re-exploration. User approve-ის შემდეგ implementation "press play" უნდა იყოს, არა "where do I start".

## ნაბიჯები

1. **Inventory** — წაიკითხე საჭირო source ფაილები, gitnexus_query/gitnexus_context relevant symbol-ებზე. **NO EDITS.**
2. **Impact analysis** — `gitnexus_impact({target, direction: "upstream"})` ყველა symbol-ისთვის რომელიც შეიცვლება. Report LOW/MED/HIGH.
3. **Scope decision** — ხომ სრული feature ერთ session-ში ვერ ჩაეტევა? Split-ი შესთავაზე.
4. **Draft preview** — დაწერე `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_{NUMBER}_{TOPIC}_PREVIEW.md` (mirror SPRINT_3B_BANK_PREVIEW.md structure):
   - **Status**: `PREVIEW · NO CODE CHANGE`
   - **Date** + **Target sprint**
   - **TL;DR** (3-5 წინადადება, plain)
   - **Inventory** — რა წავიკითხე, რა ვიპოვე
   - **Output-shape audit** (if serialization refactor) — JSON-safety ცალცალკე ცხრილში
   - **Fingerprint inputs** (if cache extension) — რა invalidate-ს cache-ს
   - **Risks / pitfalls** — 3-5 concrete gotcha
   - **Scope recommendation** — do in session / defer to next
   - **Test plan** — 7-8 integration test existing pattern-ით (`tests/test_samurneo_incremental.py` reference)
   - **Files expected to change** — precise paths + change type
   - **Self-check checklist** — pre-commit items
5. **Georgian summary user-ს** (chat-ში, 3-4 წინადადება):
   - რა ვიპოვე (1 წინადადება)
   - რისკები (1)
   - ჩემი რეკომენდაცია — do / defer / split (1)
   - "მზად ხარ იმპლემენტაციაზე?" (1)

## კრიტიკული წესები

- 🚫 **NO code changes.** მხოლოდ ერთი preview .md იწერება. production code / tests / prompts ყველაფერი უცვლელია.
- 🚫 **NO pytest runs, NO commits.**
- 🚫 **NO CONTEXT_HANDOFF.md update** (preview არაა phase closure).
- ✅ Path convention: `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_{N}_{SNAKE_CASE_TOPIC}_PREVIEW.md`
- ✅ User approves (`გამიკეთე` / `დავიწყოთ` / `კი იმპლემენტაცია`) → **next turn = implementation** (არა re-planning / re-reading preview).
- ✅ User rejects / asks for changes → update preview inline, don't start over.
- ✅ Evidence sources section-ი ბოლოში: relevant file paths + git SHA-ები, რომ შემდეგ session-ს არ სჭირდება re-exploration.

## შეხსენება

ეს command-ი არ არის "plan თვით". ეს არის **evidence-gathering-ი** რომელიც plan-ს შესაძლებელს ხდის. Plan = preview .md + user approval. Implementation = separate session.
