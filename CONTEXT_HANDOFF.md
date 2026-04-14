# CONTEXT HANDOFF — ახალი ჩატისთვის

> განახლდა: 2026-04-14 16:30 | მიზეზი: CalendarRangePicker ჩანს, მაგრამ კლიკზე არ რეაგირებს

## 🎯 მიმდინარე ამოცანა

**CalendarRangePicker უფუნქციოა — ღილაკები/პრესეტები კლიკზე არ რეაგირებს, "ნახატივით უმოძრაოა"**

## 📍 სიმპტომი

- მომხმარებელი ხსნის `http://localhost:5173/#cashflow`
- POS KPI ბარათზე აჭერს → `pos-daily-panel` იხსნება, CalendarRangePicker **ვიზუალურად ჩანს**
- **მაგრამ**: პრესეტ ღილაკები (7d/14d/30d/90d/სრული), calendar trigger ღილაკი, ყველაფერი — კლიკზე ნულოვანი რეაქცია
- "ნახატივით უმოძრაოა" — არც popup იხსნება, არც პერიოდი იცვლება
- **სხვა ყველაფერი მუშაობს** — KPI ბარათების კლიკი, პანელების გახსნა/დახურვა, ტაბების გადართვა

## ✅ რა გამოირიცხა (2 ჩატის ანალიზი)

### ჩატი 1 — Build, API, CSS ძირითადი
1. **Build** — `vite build` წარმატებით, 0 error
2. **API** — `/api/data?tab=cashflow` → 200 OK, `daily_summary` ვალიდურია
3. **pointer-events** — `.crp-bar`, `.crp-wrapper`, `.pos-daily-panel` — არცერთზე `pointer-events: none` არაა
4. **overflow** — `.panel` არ აქვს `overflow: hidden`
5. **z-index** — `.crp-popup` z-index: 500, კონფლიქტი არ ჩანს

### ჩატი 2 — სრული CSS + კოდი ანალიზი
6. **Chrome-შიც არ მუშაობს** — ❌ VS Code Simple Browser გამოირიცხა (ვარიანტი B)
7. **სხვა ინტერაქციები მუშაობს** — ❌ HMR/Cache გამოირიცხა (ვარიანტი C)
8. **CSS სრული ანალიზი** — ყველა 7 CSS ფაილი შემოწმდა:
   - `base.css` — `.panel` არ აქვს overlay, `backdrop-filter` stacking context-ს არ ქმნის კლიკის პრობლემას
   - `tables.css` — `.unmatched-bank-detail-panel` ნორმალური block, `position: static`
   - `components.css` — `.crp-*` სტილები კორექტულია
   - `responsive.css` — `mobile-bottom-nav` მხოლოდ ≤768px, `mobile-nav-overlay` მხოლოდ showAll-ზე
   - `utilities.css` — მხოლოდ print styles + drp/insights
9. **Stacking context** — `.unmatched-bank-detail-panel` და `.pos-daily-panel` siblings, overlap არ ხდება (ვარიანტი A გამოირიცხა)
10. **CalendarRangePicker.jsx** — კოდი კორექტულია: onClick handlers, useCallback deps, useEffect outside-click — ყველაფერი სწორი
11. **MobileNav** — `display: none` desktop-ზე, overlay მხოლოდ `showAll` state-ზე
12. **Global CSS** — არ არსებობს `*` selector ან global `pointer-events`/`user-select` რომელიც buttons-ს დაბლოკავდა

### გაკეთებული ცვლილება
- **availableDays მემოიზაცია** (ვარიანტი E ფიქსი): `Cashflow.jsx`-ში `posDailyAvailableDays = useMemo(...)` — ხაზი 175-178. ადრე ყოველ რენდერზე ახალი array იქმნებოდა. ეს **ოპტიმიზაციაა**, მაგრამ სავარაუდოდ root cause არ არის.

## 🔴 რა არ შემოწმდა ჯერ (PRIORITIZED)

### 1. DevTools Live Debugging (HIGHEST PRIORITY)
ბრაუზერის Playwright ინსტრუმენტი ვერ გაეშვა (browser session closed). **ხელით უნდა შემოწმდეს:**

**ნაბიჯი A — კლიკი მიდის თუ არა?**
```js
document.addEventListener('click', e => console.log('CLICK:', e.target.tagName, e.target.className), true)
```
პრესეტ ღილაკზე დააჭირე → Console-ში `CLICK: BUTTON crp-preset-btn` ჩანს?

**ნაბიჯი B — რა ელემენტია click point-ზე?**
DevTools → Elements → Ctrl+Shift+C (inspect mode) → პრესეტ ღილაკზე hover → რა ელემენტი highlight-დება? `<button>` თუ სხვა რაღაც ფარავს?

**ნაბიჯი C — Console errors?**
F12 → Console ტაბი → წითელი შეცდომები ხომ არაა?

### 2. React DevTools
Chrome-ში React DevTools extension → Components tab → CalendarRangePicker → Props:
- `availableDays` არის და სავსეა?
- `from`/`to` აქვს მნიშვნელობა?
- `onFromChange`/`onToChange` ფუნქციებია?

### 3. Inline console.log ტესტი
თუ ზემოთ ვერაფერს აჩვენებს, CalendarRangePicker.jsx-ში დამატე:
```jsx
// ხაზი 315-ის onClick-ში:
onClick={() => { console.log('PRESET CLICKED:', p.id); applyPreset(p); }}
```
და trigger button-ში (ხაზი 325):
```jsx
onClick={() => { console.log('TRIGGER CLICKED'); setOpen((v) => !v); ... }}
```

## 📁 ფაილები

### CalendarRangePicker.jsx (~399 ხაზი)
- **`rs-dashboard/src/components/CalendarRangePicker.jsx`**
- Props: `availableDays`, `from`, `to`, `onFromChange`, `onToChange`, `label`, `children`
- ხაზი 64-72: export default, props destructuring
- ხაზი 78-81: `sortedDays` useMemo — depends on `availableDays`
- ხაზი 99: `presets` useMemo — depends on `sortedDays`
- ხაზი 111-122: useEffect outside-click — `mousedown` on `document`, only when `open=true`
- ხაზი 166-174: `applyPreset` useCallback — calls `onFromChange`/`onToChange`
- ხაზი 301: `if (!sortedDays.length) return null;` — guard
- ხაზი 306-340: `.crp-bar` — პრესეტ ღილაკები + trigger button
- ხაზი 348-395: `.crp-popup` — calendar popup (renders when `open` state is true)

### Cashflow.jsx (~902 ხაზი, +5 from memo fix)
- **`rs-dashboard/src/Cashflow.jsx`**
- ხაზი 3: `import CalendarRangePicker`
- ხაზი 68: `showPosDailyTable` state (false default)
- ხაზი 72-73: `posDateFrom`, `posDateTo` state
- ხაზი 158-167: useEffect sets initial dates (setTimeout 0)
- ხაზი 169-173: `posDailySorted` useMemo
- ხაზი 175-178: **NEW** `posDailyAvailableDays` useMemo (ჩატი 2-ის ფიქსი)
- ხაზი 340: POS KPI card onClick toggles `showPosDailyTable`
- ხაზი 678-699: `showPosDailyTable` → `CalendarRangePicker` with `posDailyAvailableDays`

### App.jsx
- ხაზი 276: `<div className="panel">` — მთელი კონტენტის wrapper
- ხაზი 241-243: `showGlobalLoading` → panel ქრება, Cashflow unmount-დება (loading-ის დროს state reset!)
- ხაზი 375: `<MobileNav>` — desktop-ზე hidden

### CSS (import order: base → tables → pages → executive → components → responsive → utilities)
- `base.css:185` — `.panel { backdrop-filter: blur(12px) }` (stacking context)
- `tables.css:810` — `.pos-daily-panel { position: static, no overflow }`
- `tables.css:416` — `.unmatched-bank-detail-panel { position: static }`
- `components.css:828-1164` — `.crp-*` სტილები (ყველა კორექტული)
- `responsive.css:195` — `.mobile-bottom-nav { display: none }` (desktop)

## 🏗️ პროექტის არქიტექტურა

- **Frontend:** React 19 + Vite 8 (`rs-dashboard/`)
- **Backend:** Python FastAPI (`server.py`)
- **Data:** Excel → `generate_dashboard_data.py` → `data.json` → FastAPI → React
- **Dev server:** `npm run dev` → `http://localhost:5173/`
- **Entry:** `main.jsx` → `App.jsx` → lazy `Cashflow.jsx`
- **CSS:** `index.css` → @import base/tables/pages/executive/components/responsive/utilities

## ⚠️ კრიტიკული წესი

- ბრაუზერის ტესტი: მხოლოდ screenshot, არა snapshot
- მაქსიმუმ 3-4 browser tool call
- 80k-მდე მისვლისას მოამზადე CONTEXT_HANDOFF.md
