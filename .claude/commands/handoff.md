---
description: Handoff — context 60%-ს უახლოვდება ან სესია მთავრდება
---

# Handoff

## გააქტიურდეს: context ≥ 60% ან task დასრულდა

## ნაბიჯები:
1. გაჩერდი ლოგიკურ წერტილზე (არ დატოვო broken კოდი)
2. განაახლე `CONTEXT_HANDOFF.md` (canonical handoff ფაილი)
3. მხოლოდ თუ რეალურად შეიცვალა სტატუსი → `HANDOFF.md`, `PLAN.md`
4. დაუწერე user-ს: "CONTEXT_HANDOFF.md განახლებულია. ახალ ჩატში → 'წაიკითხე CONTEXT_HANDOFF.md'"

## კრიტიკული წესები:
- 🚫 არასოდეს შექმნა ახალი .md ფაილი
- 🚫 არ წაიკითხო HANDOFF.md / PLAN.md / PHASE_*.md თუ task-ი მათ არ სჭირდება
- 🚫 არ დატოვო broken state
- ✅ ენა: ქართული (user), ინგლისური (code/commit)
- ✅ canonical წყარო ახალი ჩატისთვის = CONTEXT_HANDOFF.md (მხოლოდ ის)
