from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


OUT = Path("out")
REPORT_DIR = OUT / "reports" / "hos_daily"
CHART_DIR = REPORT_DIR / "charts"
SNAPSHOT_GLOB = "hos_daily_market_snapshot_*.csv"
HISTORY_PATH = OUT / "hos_daily_market_history.csv"
TRAINING_SET_PATH = Path("config/f_training_set.csv")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    clean = []
    for ch in value:
        if ch.isalnum():
            clean.append(ch.lower())
        else:
            clean.append("_")
    slug = "".join(clean).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "unknown"


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _snapshot_date() -> str:
    override = os.environ.get("H_SNAPSHOT_DATE", "").strip()
    if override:
        return override
    return datetime.now(timezone.utc).date().isoformat()


def _latest_snapshot_for_date(asof_date: str) -> Path | None:
    exact = OUT / f"hos_daily_market_snapshot_{asof_date}.csv"
    if exact.exists():
        return exact
    files = sorted(OUT.glob(SNAPSHOT_GLOB))
    if not files:
        return None
    return files[-1]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _load_training_skus() -> set[str]:
    train = _read_csv(TRAINING_SET_PATH)
    if train.empty or "sku" not in train.columns:
        return set()
    if "enabled" in train.columns:
        enabled = train["enabled"].astype(str).str.strip().str.lower()
        train = train[enabled.isin({"1", "true", "yes", "y"})].copy()
    return set(train["sku"].astype(str).str.strip().str.upper().tolist())


def _plot_price(ax: plt.Axes, hist: pd.DataFrame, sku: str) -> None:
    dates = pd.to_datetime(hist["asof_date"], errors="coerce")
    bb = _to_num(hist["buy_box_price_used_gross"])
    low = _to_num(hist["lowest_offer_price_gross"])
    high = _to_num(hist["highest_offer_price_gross"])
    floor = _to_num(hist["min_price_gross_10pct"])
    ceil = _to_num(hist["max_price_gross_current"])

    ax.plot(dates, bb, marker="o", linewidth=1.5, label="Buy box used")
    ax.plot(dates, low, marker=".", linewidth=1.0, label="Lowest offer (landed)")
    ax.plot(dates, high, marker=".", linewidth=1.0, label="Highest offer (landed)")
    ax.plot(dates, floor, linestyle="--", linewidth=1.2, label="Min price 10pct")
    ax.plot(dates, ceil, linestyle="--", linewidth=1.2, label="Max price current")
    ax.set_title(f"{sku} - Price Trend", fontsize=10)
    ax.set_ylabel("Price GBP")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")


def _plot_seller_mix(ax: plt.Axes, hist: pd.DataFrame, sku: str) -> None:
    dates = pd.to_datetime(hist["asof_date"], errors="coerce")
    fba = _to_num(hist["offer_count_fba"]).fillna(0)
    fbm = _to_num(hist["offer_count_fbm"]).fillna(0)

    ax.bar(dates, fba, label="FBA", width=0.8)
    ax.bar(dates, fbm, bottom=fba, label="FBM", width=0.8)
    ax.set_title(f"{sku} - Seller Mix", fontsize=10)
    ax.set_ylabel("Offer count")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=7, loc="best")


def _sku_history(history: pd.DataFrame, row: pd.Series, snapshot_asof_date: str) -> pd.DataFrame:
    sku = _norm(row.get("sku", ""))
    marketplace = _norm(row.get("marketplace", ""))
    asin = _norm(row.get("asin", ""))
    if history.empty:
        return pd.DataFrame([row], dtype=str)

    hist = history.copy()
    for col in ["sku", "marketplace", "asin", "asof_date"]:
        if col not in hist.columns:
            hist[col] = ""

    mask = (
        hist["sku"].astype(str).str.strip().eq(sku)
        & hist["marketplace"].astype(str).str.strip().eq(marketplace)
        & hist["asin"].astype(str).str.strip().eq(asin)
    )
    out = hist.loc[mask].copy()
    if out.empty:
        out = pd.DataFrame([row], dtype=str)
    if "asof_date" not in out.columns:
        out["asof_date"] = snapshot_asof_date
    out["asof_date"] = out["asof_date"].astype(str).replace("", snapshot_asof_date)
    out = out.sort_values(["asof_date"], kind="stable")
    return out


def _build_html(
    snapshot: pd.DataFrame,
    asof_date: str,
    created_utc: str,
    rows: List[dict[str, str]],
) -> str:
    cols = [
        "sku",
        "asin",
        "buy_box_price_used_gross",
        "lowest_offer_price_gross",
        "highest_offer_price_gross",
        "offer_count_fba",
        "offer_count_fbm",
        "min_price_gross_10pct",
        "max_price_gross_current",
    ]
    display = snapshot.copy()
    for col in cols:
        if col not in display.columns:
            display[col] = ""
    table_html = display[cols].to_html(index=False, border=1)

    cards = []
    for rec in rows:
        cards.append(
            (
                "<section class='card'>"
                f"<h3>{rec['sku']} ({rec['asin']})</h3>"
                f"<img src='charts/{rec['price_chart']}' alt='Price trend chart for {rec['sku']}'/>"
                f"<img src='charts/{rec['mix_chart']}' alt='Seller mix chart for {rec['sku']}'/>"
                "</section>"
            )
        )
    cards_html = "\n".join(cards)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>HOS Daily Market Report - {asof_date}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #1a1a1a; }}
    h1 {{ margin-bottom: 0; }}
    .meta {{ margin-top: 4px; margin-bottom: 16px; color: #444; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #d0d0d0; padding: 6px; font-size: 12px; text-align: left; }}
    th {{ background: #f3f6fa; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .card {{ border: 1px solid #d9d9d9; padding: 12px; border-radius: 6px; }}
    .card h3 {{ margin-top: 0; margin-bottom: 8px; }}
    .card img {{ max-width: 100%; display: block; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>HOS Daily Market Report</h1>
  <div class="meta">As of date: {asof_date} | Created UTC: {created_utc} | Competition envelope basis: landed price (listing + shipping when available)</div>
  <h2>Daily Snapshot</h2>
  {table_html}
  <h2>Per SKU Charts</h2>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>
"""


def main() -> None:
    asof_date = _snapshot_date()
    snapshot_path = _latest_snapshot_for_date(asof_date)
    if snapshot_path is None:
        raise FileNotFoundError("No daily market snapshot found: out/hos_daily_market_snapshot_YYYY-MM-DD.csv")

    snapshot = _read_csv(snapshot_path)
    if snapshot.empty:
        raise RuntimeError(f"Daily market snapshot is empty: {snapshot_path.as_posix()}")

    history = _read_csv(HISTORY_PATH)
    for col in [
        "asof_date",
        "sku",
        "asin",
        "marketplace",
        "buy_box_price_used_gross",
        "lowest_offer_price_gross",
        "highest_offer_price_gross",
        "offer_count_fba",
        "offer_count_fbm",
        "min_price_gross_10pct",
        "max_price_gross_current",
    ]:
        if col not in snapshot.columns:
            snapshot[col] = ""
        if not history.empty and col not in history.columns:
            history[col] = ""

    if "asof_date" in snapshot.columns and snapshot["asof_date"].astype(str).str.strip().ne("").any():
        asof_date = str(snapshot["asof_date"].astype(str).str.strip().replace("", pd.NA).dropna().max())

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    rows = snapshot.sort_values(["marketplace", "sku", "asin"], kind="stable").to_dict("records")
    chart_rows: List[dict[str, str]] = []
    pdf_pages: List[tuple[str, pd.DataFrame]] = []
    price_chart_count = 0
    mix_chart_count = 0
    for row in rows:
        sku = _norm(row.get("sku", ""))
        asin = _norm(row.get("asin", ""))
        hist = _sku_history(history, pd.Series(row, dtype=str), asof_date)
        slug = _slug(f"{sku}_{asin}")
        price_chart = f"{asof_date}_{slug}_price_trend.png"
        mix_chart = f"{asof_date}_{slug}_seller_mix.png"

        fig, ax = plt.subplots(figsize=(10, 4))
        _plot_price(ax, hist, sku)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(CHART_DIR / price_chart, dpi=130)
        plt.close(fig)
        price_chart_count += 1

        fig, ax = plt.subplots(figsize=(10, 4))
        _plot_seller_mix(ax, hist, sku)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(CHART_DIR / mix_chart, dpi=130)
        plt.close(fig)
        mix_chart_count += 1

        chart_rows.append(
            {
                "sku": sku,
                "asin": asin,
                "price_chart": price_chart,
                "mix_chart": mix_chart,
            }
        )
        pdf_pages.append((sku, hist))

    html_path = REPORT_DIR / f"hos_daily_report_{asof_date}.html"
    pdf_path = REPORT_DIR / f"hos_daily_report_{asof_date}.pdf"
    index_path = REPORT_DIR / f"hos_daily_report_index_{asof_date}.csv"

    created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = _build_html(snapshot, asof_date, created_utc, chart_rows)
    html_path.write_text(html, encoding="utf-8")

    with PdfPages(pdf_path) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.0, 0.95, "HOS Daily Market Report", fontsize=16, fontweight="bold", va="top")
        ax.text(0.0, 0.90, f"As of date: {asof_date}", fontsize=11, va="top")
        ax.text(0.0, 0.86, f"Created UTC: {created_utc}", fontsize=11, va="top")
        ax.text(0.0, 0.81, f"Snapshot rows: {len(snapshot)}", fontsize=11, va="top")
        ax.text(0.0, 0.77, f"SKU charts: {len(chart_rows)}", fontsize=11, va="top")
        preview_cols = ["sku", "buy_box_price_used_gross", "min_price_gross_10pct", "max_price_gross_current"]
        preview = snapshot.copy()
        for col in preview_cols:
            if col not in preview.columns:
                preview[col] = ""
        text_lines = ["", "Snapshot preview (first 10 rows):"] + preview[preview_cols].head(10).to_string(index=False).splitlines()
        ax.text(0.0, 0.72, "\n".join(text_lines), family="monospace", fontsize=8, va="top")
        pdf.savefig(fig)
        plt.close(fig)

        for sku, hist in pdf_pages:
            fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
            _plot_price(axes[0], hist, sku)
            _plot_seller_mix(axes[1], hist, sku)
            fig.suptitle(f"{sku} - Daily Detail", fontsize=12)
            fig.autofmt_xdate()
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig)
            plt.close(fig)

    pd.DataFrame(chart_rows, dtype=str).to_csv(index_path, index=False)

    print(f"created_html={html_path.as_posix()}")
    print(f"created_pdf={pdf_path.as_posix()}")
    print(f"created_index={index_path.as_posix()}")
    print(f"snapshot_rows={len(snapshot)}")
    print(f"unique_skus={snapshot.get('sku', pd.Series(dtype=str)).astype(str).str.strip().nunique()}")
    print(f"price_chart_count={price_chart_count}")
    print(f"seller_mix_chart_count={mix_chart_count}")


if __name__ == "__main__":
    main()

