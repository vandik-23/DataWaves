# Automatic daily upload webcam images

# webcamscraper_daily.py
import os
import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests


# ==== USER CONFIG ====
# Create folder to save images
current_dir = os.getcwd()

# Go up one level (parent directory)
parent_dir = os.path.dirname(current_dir)

# Set path for 'images' folder in parent directory
save_folder = os.path.join(parent_dir, "images")

# Create the images folder if it doesn't exist
os.makedirs(save_folder, exist_ok=True)
print(f"Saving images to: {save_folder}")
os.makedirs(save_folder, exist_ok=True)

# Example: automatically scrape yesterday
start_date = datetime.now().date() - timedelta(days=1)
end_date = start_date

# set webpage and date of images 
base_url = "https://storage.roundshot.com/6166e782e2c750.93208089"

# ==== PLACE YOUR build_url FUNCTION HERE ====

def build_url(date, hour, minute):
    time_str = f"{hour:02d}-{minute:02d}-00"
    filename = f"{date}-{time_str}_full.jpg"
    url = f"{base_url}/{date}/{time_str}/{filename}"
    return url, date, time_str
# ============================================

# ---- summary counters ----
saved_count = 0
missing_count = 0            # HTTP not 200 / “not available”
error_count = 0              # Exceptions (browser/other)
errors = []                  # (date, time, msg)
misses = []                  # (date, time, status, url)

start_ts = datetime.now()
print(f"Processing window: {start_date} to {end_date}")

current_date = start_date

while current_date <= end_date:
    date = current_date.strftime("%Y-%m-%d")
    print(f"Processing date: {date}")

    for hour in range(0, 24):
        # Define minute intervals based on hour
        if 0 <= hour < 7 or 18 <= hour < 24:
            minutes = range(0, 60, 20)  # 0, 20, 40
        else:  # 7 <= hour < 18
            minutes = range(0, 60, 10)  # 0, 10, 20, 30, 40, 50

        for minute in minutes:
            url, date_part, time_part = build_url(date, hour, minute)

            # Setup Chrome options for incognito mode (as in notebook)
            chrome_options = Options()
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )

            # Initialize Selenium WebDriver
            print(f"Opening browser for {date_part} {time_part}...")
            driver = webdriver.Chrome(options=chrome_options)

            try:
                driver.get(url)
                time.sleep(random.uniform(5, 15))  # Random delay

                img_url = driver.current_url

                # Download the image
                response = requests.get(img_url)
                if response.status_code == 200:
                    clean_date_time = f"{date_part}_{time_part}".replace('-', '_')
                    filename = f"img_{clean_date_time}.png"
                    filepath = os.path.join(save_folder, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    saved_count += 1
                    print(f"Saved {filename}")
                else:
                    missing_count += 1
                    misses.append((date_part, time_part, response.status_code, img_url))
                    print(f"Image not available for {date_part} {time_part}")
                    print(img_url)

            except Exception as e:
                error_count += 1
                errors.append((date_part, time_part, str(e)))
                print(f"Error for {date_part} {time_part}: {e}")

            finally:
                driver.quit()
                print("Browser closed.")

    current_date += timedelta(days=1)

# ---- FINAL SUMMARY ----
end_ts = datetime.now()
duration = (end_ts - start_ts).total_seconds()

# Expected attempts: count how many timestamps we tried
def attempts_for_day():
    total = 0
    for hour in range(24):
        if 0 <= hour < 7 or 18 <= hour < 24:
            total += len(range(0, 60, 20))  # 3
        else:
            total += len(range(0, 60, 10))  # 6
    return total

days = (end_date - start_date).days + 1
expected_attempts = attempts_for_day() * days

print("\n================== SUMMARY ==================")
print(f"Run started: {start_ts:%Y-%m-%d %H:%M:%S}")
print(f"Run ended  : {end_ts:%Y-%m-%d %H:%M:%S}")
print(f"Duration   : {duration:.1f} seconds")
print(f"Date range : {start_date} → {end_date}  (days={days})")
print(f"Attempts   : {expected_attempts}")
print("---------------------------------------------")
print(f"Saved      : {saved_count}")
print(f"Missing    : {missing_count}")
print(f"Errors     : {error_count}")
print("=============================================\n")

# Print a short list of issues (avoid spamming logs)
MAX_SHOW = 20

if misses:
    print(f"--- Missing ({min(len(misses), MAX_SHOW)}/{len(misses)}) ---")
    for d, t, status, u in misses[:MAX_SHOW]:
        print(f"{d} {t}  [{status}]  {u}")
    if len(misses) > MAX_SHOW:
        print(f"... {len(misses) - MAX_SHOW} more missing entries not shown ...\n")

if errors:
    print(f"--- Errors ({min(len(errors), MAX_SHOW)}/{len(errors)}) ---")
    for d, t, msg in errors[:MAX_SHOW]:
        print(f"{d} {t}  ERROR: {msg}")
    if len(errors) > MAX_SHOW:
        print(f"... {len(errors) - MAX_SHOW} more errors not shown ...\n")

print("All done.")