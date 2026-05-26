import pandas as pd
from pathlib import Path
from datetime import datetime
import subprocess
import sys

def main():
    status_path = Path("Category_status.csv")
    if not status_path.exists():
        print(f"❌ File not found: {status_path.resolve()}")
        sys.exit(1)

    df = pd.read_csv(status_path)

    # --- 1️⃣  pick first row (left-to-right) that has a cell marked as "Due"
    check_columns = ["SourcingCheck", "FirstCheck", "SecondCheck"]
    pending_row = None
    pending_column = None

    for idx, row in df.iterrows():
        for col in check_columns:
            value = str(row[col]).strip().lower()
            print(f"[DEBUG] Row {idx} Column '{col}': '{value}'")  # debug output
            if value == "due":
                pending_row = idx
                pending_column = col
                break
        if pending_row is not None:
            break

    if pending_row is None:
        print("✅ No sourcing jobs due right now.")
        return

    row = df.iloc[pending_row]
    csv_file = Path("Data") / row["File"]   # adjust folder if needed

    print(f"🛠️  Starting sourcing for: {row['keyword']} (column: {pending_column})  →  {csv_file}")

    # Decide which script to run based on the pending column
    if pending_column == "SourcingCheck":
        script = "newProductSourcing.py"
    elif pending_column == "FirstCheck":
        script = "newProductFirstCheck.py"
    elif pending_column == "SecondCheck":
        script = "newProductSecondCheck.py"
    else:
        print("❌ Unknown sourcing column.")
        sys.exit(1)

    # --- 2️⃣  run the appropriate sourcing script ---
    try:
        subprocess.run(
            ["python", script, "--scan-file", str(csv_file)],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ Sourcing script failed – status not updated.")
        sys.exit(1)

    # --- 3️⃣  mark the due cell (for the pending column) as completed using today's date ---
    df.at[pending_row, pending_column] = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(status_path, index=False)
    print("✅ Sourcing completed and status file updated.")

if __name__ == "__main__":
    main()
