#!/usr/bin/env python3
"""
ბანკის დებეტის რეკონცილიაცია: Excel-ის ჯამი = მიბმული + არამიბმული (get_bank_payments-ის იგივე ლოგიკა).

გაშვება პროექტის ფესვიდან:
  python verify_reconciliation.py

წარმატება: exit 0; სხვაობა: წითელი შეტყობინება და exit 1.
"""
import os
import sys

# პროექტის ფესვი
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from generate_dashboard_data import get_bank_payments, list_rs_waybill_files  # noqa: E402


def main():
    rs_files = list_rs_waybill_files()
    _, _, ok = get_bank_payments(rs_files, reconciliation_exit_on_fail=False)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
