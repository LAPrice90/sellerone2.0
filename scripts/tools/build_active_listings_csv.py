from __future__ import annotations

import argparse
import csv
from pathlib import Path


SKU_COLUMN_CANDIDATES = [
    "sku",
    "SKU",
    "seller-sku",
    "seller_sku",
    "Seller SKU",
    "SellerSKU",
]
DEFAULT_OUTPUT = Path("out/active_listings.csv")
RECOMMENDED_EXPORT_PATH = Path(r"C:\Users\Luke\Downloads\ManageInventoryExport.csv")


def _norm(text: object) -> str:
    return str(text or "").strip()


def _norm_header(text: object) -> str:
    return _norm(text).lower().replace("-", "").replace("_", "").replace(" ", "")


def _sniff_delimiter(sample_text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",\t")
        if getattr(dialect, "delimiter", ",") in {",", "\t"}:
            return dialect.delimiter
        return ","
    except Exception:
        return ","


def _open_reader(path: Path) -> tuple[csv.DictReader, object]:
    last_error: Exception | None = None
    for enc in ("utf-8-sig", "cp1252", "utf-8"):
        try:
            fh = path.open("r", encoding=enc, newline="")
            sample = fh.read(4096)
            fh.seek(0)
            delimiter = _sniff_delimiter(sample)
            # Keep quote behavior deterministic; only sniff delimiter.
            return csv.DictReader(fh, delimiter=delimiter, quotechar='"', doublequote=True), fh
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"could not read input file: {path} ({last_error})")


def _resolve_sku_column(fieldnames: list[str], override: str) -> str:
    if not fieldnames:
        raise RuntimeError("input file has no header row")
    by_norm = {_norm_header(col): col for col in fieldnames if _norm(col)}
    if _norm(override):
        wanted = _norm_header(override)
        resolved = by_norm.get(wanted, "")
        if not resolved:
            raise RuntimeError(
                f"--sku-col '{override}' not found in input headers. "
                f"Available: {', '.join([_norm(c) for c in fieldnames if _norm(c)])}"
            )
        return resolved

    matches: list[str] = []
    for cand in SKU_COLUMN_CANDIDATES:
        resolved = by_norm.get(_norm_header(cand), "")
        if resolved:
            if resolved not in matches:
                matches.append(resolved)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise RuntimeError(
            "auto-detect found multiple SKU columns; refusing to choose. "
            f"Candidates: {', '.join(matches)}. Re-run with --sku-col."
        )
    raise RuntimeError(
        "could not find SKU column in input. Tried: " + ", ".join(SKU_COLUMN_CANDIDATES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build out/active_listings.csv from Amazon Manage Inventory export."
    )
    parser.add_argument("--input", required=True, help="Path to Amazon export CSV/TSV")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output path (default: out/active_listings.csv)")
    parser.add_argument("--sku-col", default="", help="Optional explicit SKU column name (case-insensitive)")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    if not input_path.exists():
        print(
            "[ERROR] Active listings export file not found.\n"
            f"- Expected input: {input_path}\n"
            f"- Export the Amazon Manage Inventory report to: {RECOMMENDED_EXPORT_PATH}\n"
            f"- Then run again with: --input \"{RECOMMENDED_EXPORT_PATH}\""
        )
        return 2

    reader, fh = _open_reader(input_path)
    try:
        sku_col = _resolve_sku_column(list(reader.fieldnames or []), _norm(args.sku_col))
        seen: set[str] = set()
        rows: list[list[str]] = []
        for row in reader:
            sku = _norm(row.get(sku_col, "")).upper()
            if not sku or sku in seen:
                continue
            seen.add(sku)
            rows.append([sku])
    finally:
        fh.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as out_fh:
        writer = csv.writer(out_fh)
        writer.writerow(["sku"])
        writer.writerows(rows)

    print(
        "active_listings_export "
        f"input={input_path} output={output_path} "
        f"sku_col={sku_col} active_count={len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
