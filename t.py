import requests
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ---------------- CONFIG ----------------
START_ID = 114450
END_ID = 170000
BASE_URL = "https://www.taxsutra.com/download/attachment-conclusion/{}"
DOWNLOAD_DIR = "t_downloads"          # ← CHANGED from "downloads"

DELAY_MIN = 3
DELAY_MAX = 6

MAX_RETRIES = 3
MAX_WORKERS = 1                        # ← CHANGED from 3
MIN_GAP = 2
# ----------------------------------------

FAILED_CSV = os.path.join(DOWNLOAD_DIR, "failed_ids.csv")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Write header only if CSV doesn't exist yet
if not os.path.exists(FAILED_CSV):
    with open(FAILED_CSV, "w") as f:
        f.write("failed_id\n")

# ← REMOVED: Tor proxy block deleted entirely

# Global rate limiter
_last_request_time = 0
_rate_lock = threading.Lock()

def rate_limited_sleep():
    global _last_request_time
    with _rate_lock:
        now = time.time()
        gap = now - _last_request_time
        if gap < MIN_GAP:
            time.sleep(MIN_GAP - gap)
        _last_request_time = time.time()

# Each thread gets its own session (thread-safe)
def make_session():
    session = requests.Session()
    # ← REMOVED: session.proxies.update(proxies)
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session

def is_pdf(response):
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" in content_type.lower():
        return True
    if response.content[:4] == b"%PDF":
        return True
    return False

def is_error_page(response):
    return "unexpected error" in response.text.lower()

failed_lock = threading.Lock()

def log_failed_id(file_id):
    with failed_lock:
        with open(FAILED_CSV, "a", newline="") as f:
            f.write(f"{file_id}\n")

def download_file(file_id):
    file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.pdf")

    if os.path.exists(file_path):
        print(f"[SKIP EXISTS] {file_id}")
        return

    session = make_session()
    url = BASE_URL.format(file_id)

    for attempt in range(MAX_RETRIES):
        try:
            rate_limited_sleep()
            print(f"[CHECKING] {file_id}")
            response = session.get(url, timeout=30)

            if response.status_code != 200:
                print(f"[STATUS FAIL] {file_id}")
                break

            if is_pdf(response):
                with open(file_path, "wb") as f:
                    f.write(response.content)
                print(f"[DOWNLOADED] {file_id}")

            elif is_error_page(response):
                print(f"[NO FILE] {file_id}")

            else:
                print(f"[UNKNOWN RESPONSE] {file_id}")

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            break

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Attempt {attempt+1} for {file_id} -> {e}")
            time.sleep(10)

    else:
        print(f"[FAILED AFTER RETRIES] {file_id}")
        log_failed_id(file_id)

# ---- THREADING WRAPPER ----
def main():
    all_ids = range(START_ID, END_ID + 1)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_file, fid): fid for fid in all_ids}
        for future in as_completed(futures):
            pass

if __name__ == "__main__":
    main()
