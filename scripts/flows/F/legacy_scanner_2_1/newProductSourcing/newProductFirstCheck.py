# newProductFirstCheck.py
import time, csv
from pathlib import Path
from datetime import datetime
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.common.exceptions import TimeoutException


INPUT_CSV   = Path("product_discovery_output.csv")  # adjust if needed
DATE_STR    = datetime.now().strftime("%Y-%m-%d")

# ---------- helper: login once ----------
def login_to_buybotpro(driver, email, password):
    iframe = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "bbp-frame"))
    )
    driver.switch_to.frame(iframe)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#loginEmail"))
    ).send_keys(email)
    driver.find_element(By.CSS_SELECTOR, "#loginPassword").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "#loginBtn").click()
    driver.switch_to.default_content()
    time.sleep(4)

# ---------------- safe UC launch ----------------
import undetected_chromedriver as uc
from pathlib import Path

def launch_driver_uc():
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.binary_location = r"C:\Chrome_UC136v2\bin\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136v2")
    options.add_argument(r"--profile-directory=BBPProfile157")


    return uc.Chrome(
        options=options,
        version_main=136,
        driver_executable_path=r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver\136.0.7103.4800-beta\driver\win32\chromedriver.exe"
    )




# ---------------- MAIN ------------------
def main() -> None:
    if not INPUT_CSV.exists():
        print(f"❌ Input file not found: {INPUT_CSV}")
        return

    while True:
        # Reload CSV for the latest updates
        df = pd.read_csv(INPUT_CSV)
        # Ensure the column exists and is string-compatible
        if "AmazonSelling" not in df.columns:
            df["AmazonSelling"] = ""
        else:
            df["AmazonSelling"] = df["AmazonSelling"].fillna("").astype(str)

        # Find the next unprocessed row (where "AmazonSelling" is blank)
        mask = df["AmazonSelling"].str.strip() == ""
        if not mask.any():
            print("✅ All ASINs already first-checked.")
            break

        next_row = df[mask].iloc[0]
        row_idx = next_row.name  # index in DataFrame
        asin = next_row["asin"]

        print(f"🔍 Next blank value found at row {row_idx} in column 'AmazonSelling'. ASIN: {asin}")

        # Proceed without marking the cell as "processing"
        # (Optionally, log that we are proceeding with processing the ASIN)
        
        driver.get(f"https://www.amazon.co.uk/dp/{asin}")
        time.sleep(3)  # allow the page to load

        # Check if the BBP iframe exists – if so, do login
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "bbp-frame"))
            )
            login_to_buybotpro(driver, "dan@drjhardware.co.uk", "Systembox-60811963")
        except TimeoutException:
            print(f"⚠️  Login not needed on ASIN {asin}")

        # Attempt the BBP/primeOnly click
        try:
            prime_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="primeOnly"]'))
            )
            prime_btn.click()
            time.sleep(2)
        except Exception as e:
            print(f"⚠️  BBP/primeOnly issue on ASIN {asin} ⇒ {e}", flush=True)
            print("🔄 Refreshing page and retrying BBP/primeOnly click...", flush=True)
            driver.refresh()
            time.sleep(3)
            try:
                prime_btn = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="primeOnly"]'))
                )
                prime_btn.click()
                time.sleep(2)
            except Exception as e2:
                print(f"⚠️  Retry BBP/primeOnly issue on ASIN {asin} ⇒ {e2}", flush=True)

        # Retrieve and process BSR & Prices
        try:
            bsr_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="bsrAndPricesName"]'))
            )
            bsr_text = bsr_element.text.strip()
            print(f"DEBUG: Outer HTML for ASIN {asin}: {bsr_element.get_attribute('outerHTML')}", flush=True)
            print(f"ASIN {asin} BSR & Prices: '{bsr_text}'", flush=True)
            if bsr_text == "Amazon":
                df.loc[df["asin"] == asin, "AmazonSelling"] = "Yes"
                print(f"✅ ASIN {asin}: Selling by Amazon — marked Yes", flush=True)
            else:
                df.loc[df["asin"] == asin, "AmazonSelling"] = "No"
                print(f"❌ ASIN {asin}: Not sold by Amazon — marked No", flush=True)
                # If result is empty (interpreted as 0), attempt the second test: compute average of statistics
                if bsr_text == "":
                    numbers = []
                    xpaths = [
                        '//*[@id="asinAverageStatisticsDataTable"]/tbody/tr[4]/td[2]',
                        '//*[@id="asinAverageStatisticsDataTable"]/tbody/tr[4]/td[3]',
                        '//*[@id="asinAverageStatisticsDataTable"]/tbody/tr[4]/td[4]',
                        '//*[@id="asinAverageStatisticsDataTable"]/tbody/tr[4]/td[5]'
                    ]
                    for xpath in xpaths:
                        try:
                            cell = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, xpath))
                            )
                            text = cell.text.strip().replace(",", "")
                            if text:
                                number = float(text)
                                numbers.append(number)
                        except Exception as e:
                            print(f"⚠️ Error retrieving statistics cell for xpath {xpath}: {e}", flush=True)
                    if numbers:
                        avg = sum(numbers) / len(numbers)
                        print(f"[DEBUG] Average statistics for ASIN {asin}: {avg}", flush=True)
                        # Paste the average into the ASIN's row under the PrivateLabel column
                        df.loc[df["asin"] == asin, "PrivateLabel"] = avg
        except Exception as e:
            print(f"⚠️  Issue retrieving BSR & Prices for ASIN {asin} ⇒ {str(e)}", flush=True)
            df.loc[df["asin"] == asin, "AmazonSelling"] = "ERROR"

        # Save the updated CSV after processing one ASIN
        df.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
        print("✅ CSV updated with AmazonSelling results.")
        time.sleep(1)


def launch_bbp_driver():
    options = uc.ChromeOptions()
    options.binary_location = r"C:\Chrome_UC136v2\bin\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136v2")
    options.add_argument(r"--profile-directory=BBPProfile1")

    driver = uc.Chrome(
        options=options,
        version_main=136,
        browser_executable_path=r"C:\Chrome_UC136v2\bin\chrome.exe",
        driver_executable_path=r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver\136.0.7103.4800-beta\driver\win32\chromedriver.exe"
    )
    driver.set_window_position(0, 0)
    driver.set_window_size(1280, 720)
    return driver


def patch_chrome_driver(driver):
    uc.Chrome = lambda *ar8080gs, **kwargs: driver

if __name__ == "__main__":
    print("[INFO] Launching Chrome for BBP scan…")
    driver = launch_bbp_driver()
    patch_chrome_driver(driver)

    try:
        main()
    finally:
        print("[INFO] Closing Chrome.")
        driver.quit()
