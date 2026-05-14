---
description: Restart FinancialDashboardBackend NSSM service (UAC elevation required)
---

# /restart-service — Restart backend pipeline service

## როდის გააქტიურდეს

- Pipeline-ის (server.py, generate_dashboard_data.py, dashboard_pipeline/*) ცვლილების შემდეგ
- API contract changes (api_contracts.py, FIELD_DEFAULTS, TAB_ALLOWLIST)
- ახალი MCP-style endpoint დამატება
- ნებისმიერი .py ფაილი, რომელიც FastAPI app-ში იტვირთება

## რას აკეთებს

ერთი ბრძანებით აშორებს ხელით PowerShell გახსნის + admin escalation-ის + UAC prompt-ის + ბრძანების აკრეფის ციკლს.

NSSM სერვისი `FinancialDashboardBackend` ხელახლა იწყება, port 8000 ხელახლა იხსნება ახალი კოდით.

## ნაბიჯები

1. გაუშვი ეს PowerShell ბრძანება (admin elevation ხდება ავტომატურად):

```powershell
Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-Command', 'Restart-Service FinancialDashboardBackend; Write-Host "Service restarted at $(Get-Date)"; Start-Sleep -Seconds 3'
```

2. დააცადე 3-5 წამი — სერვისი ჩერდება და იწყება.

3. შემოწმე რომ port 8000 ხელახლა გაიხსნა:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/data?tab=meta" -TimeoutSec 10 | Select-Object -ExpandProperty StatusCode
```

მოლოდინი: `200`.

4. თუ status 200-ია — სერვისი წესრიგშია.
   თუ ცდება — `Get-Service FinancialDashboardBackend` ვამოწმოთ, რომ Status = Running.

## კრიტიკული წესები

- 🚫 **არ გამოიყენო** კოდის ცვლილების გარეშე — UAC prompt-ი user-ის ფოკუსს არღვევს, არასაჭიროდ არ უნდა აიწიოს.
- 🚫 **არ შეცვალო** NSSM-ის სხვა settings (Restart-Service ერთადერთი action-ი).
- ✅ User-ს UAC dialog ჩნდება — ის უნდა დათანხმდეს. ეს Windows-ის უსაფრთხოების მოთხოვნაა, ვერ აიცილებთ.
- ✅ თუ UAC უარყოფითია — service არ გადატვირთულა, შეტყობინება დაბრუნდება და სცადო ცხადი fallback (manual NSSM restart instruction).

## შენიშვნა

NSSM სერვისის სახელი fixed-ია: `FinancialDashboardBackend`. თუ პროექტი სხვა ბილდინგ-ში ან სხვა სერვისით მუშაობს, ეს command უნდა შესწორდეს.
