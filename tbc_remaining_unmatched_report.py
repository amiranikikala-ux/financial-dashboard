import os
import re
import pandas as pd


def _norm_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def _signature(text):
    s = _norm_text(text).lower()
    s = re.sub(r"ge\d{2}[a-z0-9]{8,}", "IBAN", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{6,}\b", "N", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:180]


def main():
    base_dir = r"c:\Users\tengiz\OneDrive\Desktop\AI აგენტი"
    src = os.path.join(base_dir, "download", "ბანკი_არამიბმული_ხაზები.xlsx")
    out = os.path.join(base_dir, "download", "TBC_დარჩენილი_არამიბმული_ანალიზი.xlsx")

    if not os.path.isfile(src):
        print(f"Source not found: {src}")
        return

    df = pd.read_excel(src)
    if df.empty:
        print("Source file is empty.")
        return

    bank_col = "ბანკი" if "ბანკი" in df.columns else None
    amount_col = "თანხა" if "თანხა" in df.columns else None
    date_col = "თარიღი" if "თარიღი" in df.columns else None
    name_col = "მიმღები_სახელი" if "მიმღები_სახელი" in df.columns else None
    desc_col = "ოპერაციის_შინაარსი" if "ოპერაციის_შინაარსი" in df.columns else None

    if not bank_col or not amount_col:
        print("Expected columns not found in unmatched file.")
        return

    tbc = df[df[bank_col].astype(str).str.upper().eq("TBC")].copy()
    if tbc.empty:
        print("No TBC unmatched rows found.")
        return

    tbc[amount_col] = pd.to_numeric(tbc[amount_col], errors="coerce").fillna(0.0)
    if desc_col and name_col:
        tbc["signature"] = (
            tbc[name_col].map(_norm_text) + " | " + tbc[desc_col].map(_norm_text)
        ).apply(_signature)
    elif name_col:
        tbc["signature"] = tbc[name_col].apply(_signature)
    elif desc_col:
        tbc["signature"] = tbc[desc_col].apply(_signature)
    else:
        tbc["signature"] = ""
    if date_col:
        dt = pd.to_datetime(tbc[date_col], errors="coerce")
        tbc["month"] = dt.dt.to_period("M").astype(str)
    else:
        tbc["month"] = ""

    # Top groupings for "what remains"
    top_receivers = (
        tbc.groupby(name_col, dropna=False)[amount_col]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={name_col: "მიმღები_სახელი", "count": "ხაზები", "sum": "ჯამი"})
        .sort_values(["ჯამი", "ხაზები"], ascending=[False, False])
    ) if name_col else pd.DataFrame()

    top_signatures = (
        tbc.groupby("signature", dropna=False)[amount_col]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"signature": "სიგნატურა", "count": "ხაზები", "sum": "ჯამი"})
        .sort_values(["ჯამი", "ხაზები"], ascending=[False, False])
    )

    monthly = (
        tbc.groupby("month", dropna=False)[amount_col]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"month": "თვე", "count": "ხაზები", "sum": "ჯამი"})
        .sort_values("თვე", ascending=True)
    )

    summary = pd.DataFrame(
        [
            {"მაჩვენებელი": "TBC არამიბმული ხაზები", "მნიშვნელობა": int(len(tbc))},
            {"მაჩვენებელი": "TBC არამიბმული ჯამი", "მნიშვნელობა": float(tbc[amount_col].sum())},
            {"მაჩვენებელი": "უნიკალური მიმღები", "მნიშვნელობა": int(tbc[name_col].nunique(dropna=True) if name_col else 0)},
            {"მაჩვენებელი": "უნიკალური სიგნატურა", "მნიშვნელობა": int(top_signatures["სიგნატურა"].nunique(dropna=True))},
        ]
    )

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        summary.to_excel(xw, index=False, sheet_name="შეჯამება")
        tbc.to_excel(xw, index=False, sheet_name="TBC_დარჩენილი_ხაზები")
        if not top_receivers.empty:
            top_receivers.head(200).to_excel(xw, index=False, sheet_name="TOP_მიმღებები")
        top_signatures.head(300).to_excel(xw, index=False, sheet_name="TOP_სიგნატურები")
        monthly.to_excel(xw, index=False, sheet_name="თვიური")

    print(f"TBC unmatched lines: {len(tbc)}")
    print(f"TBC unmatched total: {tbc[amount_col].sum():,.2f}")
    print(f"Saved report: {out}")


if __name__ == "__main__":
    main()
