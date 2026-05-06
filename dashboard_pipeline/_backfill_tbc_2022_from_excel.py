"""One-shot: import TBC 2022 Excel into parquet cache so pipeline sees it.

Why this exists:
  pipeline reads Financial_Analysis/cache/tbc/*.parquet; cache only has
  2023-2026. TBC 2022 raw Excel is sitting unused. This backfills it so
  bank_reconciliation can match pre-2023 supplier payments.

Idempotent: append_tbc_cache dedupes by transaction_id.
"""
import sys
from pathlib import Path
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

TBC_2022 = _PROJECT_ROOT / "Financial_Analysis" / "თბს ბანკი ამონაწერი" / "2022.xlsx"


def main():
    print(f"Reading {TBC_2022.name}...")
    # Sheet has headers in row 0 (Georgian) + row 1 (English) — pandas takes row 0
    df = pd.read_excel(TBC_2022, header=0)
    # Drop the English-header row if it slipped in as a data row
    if not df.empty and "Date" in str(df.iloc[0].to_dict().values()):
        df = df.iloc[1:].reset_index(drop=True)
    # Or: drop rows where "Paid Out" appears in the debit column literally
    debit_col = "გასული თანხა"
    if debit_col in df.columns:
        df = df[~df[debit_col].astype(str).str.contains("Paid|Out|Amount", case=False, na=False)]
    print(f"  {len(df):,} rows after header cleanup")

    from dashboard_pipeline.tbc_cache import append_tbc_cache, read_tbc_cache
    added = append_tbc_cache(df)
    print(f"  appended: {added}")

    # Verify
    df_2022 = read_tbc_cache(2022)
    print(f"  2022 cache after: {len(df_2022):,} rows")
    if not df_2022.empty:
        print(f"  date range: {df_2022['თარიღი'].min()} .. {df_2022['თარიღი'].max()}")


if __name__ == "__main__":
    main()
