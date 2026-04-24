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
4. დაუწერე user-ს: "CONTEXT_HANDOFF.md განახლებულია. ახალ ჩატში → 'წაიკითხე CONTEXT_HANDOFF.md'"

## კრიტიკული წესები:
- 🚫 არასოდეს შექმნა ახალი .md ფაილი (გარდა `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_XX_NAME_PREVIEW.md`-ისა sprint preview-სთვის)
- 🚫 არ წაიკითხო `PHASE_STATUS_MATRIX.md` / `HANDOFF.md` თუ task-ი მათ არ სჭირდება — `CONTEXT_HANDOFF.md`-ში ყველაფერი მოკლედაა
- 🚫 არ დატოვო broken state
- 🚫 არ განაახლო `HANDOFF.md` / `PHASE_STATUS_MATRIX.md` session history-თი — მათი role სხვაა (pointer / phase overview)
- ✅ ენა: ქართული (user), ინგლისური (code/commit)
- ✅ canonical წყარო ახალი ჩატისთვის = **CONTEXT_HANDOFF.md** (მხოლოდ ის)
