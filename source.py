import os
import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style, init
import threading

# Initialize colorama for Windows compatibility
init(autoreset=True)

# Constants
MOJANG_API_URL = "https://api.mojang.com/users/profiles/minecraft/"
SLEEP_DURATION = 1  # seconds
MAX_RETRIES = 3  # Retry limit for rate-limiting
SAFE_DIRECTORY = os.path.abspath("user_files")  # Trusted directory for files
THREAD_POOL_SIZE = 5  # Limit concurrent threads

# Logging setup with the new format
logging.basicConfig(filename="username_check.log", level=logging.INFO, format="%(message)s")

# Semaphore for rate-limiting
rate_limiter = threading.Semaphore(THREAD_POOL_SIZE)
available_names_lock = threading.Lock()

def sanitize_filename(input_filename):
    safe_path = os.path.abspath(os.path.join(SAFE_DIRECTORY, input_filename))
    if not safe_path.startswith(SAFE_DIRECTORY):
        raise ValueError("Invalid file path. Directory traversal attempt detected!")
    return safe_path

def validate_username(username):
    if len(username) < 3 or len(username) > 16 or " " in username:
        print(f"{Fore.RED}Invalid username: {username}. Must be between 3-16 characters without spaces.{Style.RESET_ALL}")
        return False
    return True

def get_usernames_from_file():
    while True:
        filename = input(f"\n{Fore.YELLOW}Enter the filename containing usernames:{Style.RESET_ALL} ").strip()
        if filename:
            try:
                sanitized_filename = sanitize_filename(filename)
                with open(sanitized_filename, "r") as file:
                    usernames = [line.strip() for line in file if line.strip()]
                if usernames:
                    return usernames
                else:
                    print(f"{Fore.RED}The file is empty! Try again.{Style.RESET_ALL}")
            except (FileNotFoundError, ValueError) as e:
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Filename cannot be empty! Try again.{Style.RESET_ALL}")

def get_usernames_manually():
    while True:
        usernames = input(f"\n{Fore.YELLOW}Enter the usernames you want to check for, separate them with commas (name1,name2):{Style.RESET_ALL} ").split(",")
        usernames = [name.strip() for name in usernames if name.strip()]
        usernames = [name for name in usernames if validate_username(name)]
        if usernames:
            return usernames
        print(f"{Fore.RED}No valid usernames entered! Try again.{Style.RESET_ALL}")

def check_username(session, username):
    url = f"{MOJANG_API_URL}{username}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with rate_limiter:
                start_time = time.time()
                response = session.get(url)
                response_time = round(time.time() - start_time, 3)

            log_entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Response for {username}: {response_time}s"

            if response.status_code == 200:
                logging.info(f"{log_entry}\n>> Username not available")
                return f"{Fore.RED}{username} is TAKEN{Style.RESET_ALL}"
            elif response.status_code == 404:
                logging.info(f"{log_entry}\n>> Username is available")
                return f"{Fore.GREEN}{username} is AVAILABLE{Style.RESET_ALL}"
            elif response.status_code == 429:
                wait_time = SLEEP_DURATION * attempt
                print(f"{Fore.YELLOW}Rate-limited! Retrying in {wait_time} seconds...{Style.RESET_ALL}")
                time.sleep(wait_time)
            else:
                logging.warning(f"{log_entry}\n>> Unexpected response: {response.status_code}")
                return f"{Fore.YELLOW}Unexpected response for {username} ({response.status_code}){Style.RESET_ALL}"
        except requests.RequestException as e:
            logging.error(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error checking {username}: {e}")
            return f"{Fore.YELLOW}Error checking {username}: {e}{Style.RESET_ALL}"

    logging.warning(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Failed to check {username} after multiple attempts")
    return f"{Fore.YELLOW}Failed to check {username} after multiple attempts{Style.RESET_ALL}"

def save_available_usernames(available_names):
    output_filename = sanitize_filename("available_usernames.txt")
    if os.path.exists(output_filename):
        overwrite = input(f"{Fore.YELLOW}File {output_filename} already exists. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print(f"{Fore.RED}Aborted. File not overwritten.{Style.RESET_ALL}")
            return

    try:
        with open(output_filename, "w") as file:
            file.write("\n".join(available_names))
        print(f"\n{Fore.CYAN}Available usernames saved to {output_filename}{Style.RESET_ALL}")
    except IOError as e:
        print(f"{Fore.RED}Error writing to file: {e}{Style.RESET_ALL}")

def main():
    print(f"{Fore.CYAN}MCNameChecker - Developed by -blaze.{Style.RESET_ALL}")
    print(f"If you have any questions/suggestions/need help with anything, message me on Discord @ vichonder.\n")
    
    while True:
        print(f"{Fore.YELLOW}Press 1 for Manual Username Checking.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Press 2 for File Name Checking.{Style.RESET_ALL}")
        
        choice = input("\nEnter your choice (1 or 2): ").strip()
        
        if choice == "1":
            usernames = get_usernames_manually()
        elif choice == "2":
            usernames = get_usernames_from_file()
        else:
            print(f"{Fore.RED}Invalid choice! Please enter 1 or 2.{Style.RESET_ALL}")
            continue

        available_names = []

        with requests.Session() as session:
            with ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
                futures = {executor.submit(check_username, session, name): name for name in usernames}
                total_usernames = len(usernames)
                processed_count = 0
                for future in as_completed(futures):
                    result = future.result()
                    print(result)
                    if "AVAILABLE" in result:
                        with available_names_lock:
                            available_names.append(futures[future])
                    processed_count += 1
                    print(f"{Fore.CYAN}Processing... {processed_count}/{total_usernames} usernames checked.{Style.RESET_ALL}")
                    time.sleep(SLEEP_DURATION)

        if available_names:
            save_available_usernames(available_names)
        else:
            print(f"\n{Fore.YELLOW}No available usernames found.{Style.RESET_ALL}")

        while True:
            continue_choice = input("\nContinue checking? (Y/N): ").strip().lower()
            if continue_choice == "y":
                break  # Restart from the menu
            elif continue_choice == "n":
                print(f"{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
                return  # Exit program
            else:
                print(f"{Fore.RED}Invalid choice! Enter Y or N.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
