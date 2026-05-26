import pandas as pd

# Load the CSV
df = pd.read_csv("product_discovery_output.csv")

# Ensure the AmazonSelling column exists
if "AmazonSelling" not in df.columns:
    df["AmazonSelling"] = ""

# Update the row where ASIN is B0DF6DW49G
df.loc[df["asin"] == "B0DF6DW49G", "AmazonSelling"] = "Yes"

# Save it
df.to_csv("product_discovery_output.csv", index=False, encoding="utf-8-sig")
print("✅ Updated AmazonSelling column.")
