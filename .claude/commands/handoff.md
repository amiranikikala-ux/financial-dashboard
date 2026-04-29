---
description: Handoff — context 60%-ს უახლოვდება ან სესია მთავრდება
---

# Handoff

## გააქტიურდეს: context ≥ 60% ან task დასრულდა

## ნაბიჯები:
1. გაჩერდი ლოგიკურ წერტილზე (არ დატოვო broken კოდი)
2. განაახლე `CONTEXT_HANDOFF.md` (canonical ცოცხალი სტატუსი — სესიაზე **ერთადერთი** ფაილი რომელიც ცხადად განაახლდება)
3. მხოლოდ თუ **phase / sprint დაიხურა**:
   - `PHASE_STATUS_MATRIX.md` — სტატუსი `📋 PLANNED` → `✅`/`🎬`
   - `HANDOFF.md` — commit SHA → archive pointer (თუ preview-ი არქივში გადადის)
4. დაუწერე user-ს მოკლედ: „CONTEXT_HANDOFF.md განახლდა — შეჯამება: [რა შევცვალე §-ების მიხედვით]". **NEVER** უთხრა „ახალ ჩატში → 'წაიკითხე CONTEXT_HANDOFF.md'" — `.claude/settings.json`-ში SessionStart hook ავტომატურად კითხულობს `session_start_reminder.json`-ს, რომელიც BLOCKING message-ით აიძულებს ახალ ჩატს წაიკითხოს CONTEXT_HANDOFF + MASTER_PLAN + AGENTS ვიდრე პირველ tool-ს გამოიყენებს. ხელით instruction-ის მიცემა redundant + confusing + auto-system-ის ნდობას არღვევს.

## კრიტიკული წესები:
- 🚫 არასოდეს შექმნა ახალი .md ფაილი (გარდა `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_XX_NAME_PREVIEW.md`-ისა sprint preview-სთვის)
- 🚫 არ წაიკითხო `PHASE_STATUS_MATRIX.md` / `HANDOFF.md` თუ task-ი მათ არ სჭირდება — `CONTEXT_HANDOFF.md`-ში ყველაფერი მოკლედაა
- 🚫 არ დატოვო broken state
- 🚫 არ განაახლო `HANDOFF.md` / `PHASE_STATUS_MATRIX.md` session history-თი — მათი role სხვაა (pointer / phase overview)
- 🚫 **არასოდეს უთხრა user-ს ხელით ბრძანების ჩაწერა, რომელიც hook-ით ავტომატდება** — SessionStart hook-ის გადარჩევა + redundant manual step = ნდობის რღვევა (ფიქსირდა 2026-04-30, fix landed in v1.1)
- ✅ ენა: ქართული (user), ინგლისური (code/commit)
- ✅ canonical წყარო ახალი ჩატისთვის = **CONTEXT_HANDOFF.md** (SessionStart hook-ით auto-loaded)
