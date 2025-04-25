import aiohttp
from typing import List, Tuple
from src.helpers.proxyManager import ProxyManager
import asyncio
import time
import json
import random

import os

from fake_useragent import UserAgent

class EvmEngine:
    def __init__(self):
        self.max_concurrent_requests = 40
        self.api_rate_limit = self.max_concurrent_requests
        self._rate_limiter = asyncio.Semaphore(self.api_rate_limit)
        self._last_request_time = 0
        self._request_interval = 1.0 / self.api_rate_limit
        self._lock = asyncio.Lock()
        self.proxy_manager = ProxyManager()

    async def get_balances(self, holders: list[str]) -> List[Tuple[str, str]]:
        balances: List[Tuple[str, str]] = []
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        total_holders = len(holders)
        processed_count = 0

        async def process_holder(holder: str) -> Tuple[str, str]:
            nonlocal processed_count
            async with semaphore:
                try:
                    result = await self.__get_balance(holder)
                    processed_count += 1
                    print(f"Processed {processed_count} of {total_holders} wallets")
                    return (holder, str(result))
                except Exception as e:
                    processed_count += 1
                    print(f"Error processing wallet {holder}: {str(e)}")
                    return (holder, "0")

        tasks = [process_holder(holder) for holder in holders]

        try:
            # Обрабатываем результаты по мере их завершения
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    balances.append(result)
                except asyncio.CancelledError:
                    print("❌ Задача отменена. Возвращаю частичные результаты...")
                    return balances
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    print(f"❌ Сетевая ошибка в задаче: {str(e)}. Продолжаю с частичными результатами...")
                    continue  # Продолжаем обработку остальных задач
                except Exception as e:
                    print(f"❌ Неожиданная ошибка в задаче: {str(e)}. Продолжаю...")
                    continue
        except KeyboardInterrupt:
            print("❌ Процесс прерван пользователем (Ctrl+C). Возвращаю частичные результаты...")
            # Отменяем все задачи
            for task in tasks:
                task.cancel()
            return balances
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"❌ Сетевая ошибка: {str(e)}. Возвращаю частичные результаты...")
            return balances

        return balances

    async def __get_balance(self, holder: str) -> float:
        proxy = self.proxy_manager.get_proxy()

        url = "https://app.zerion.io/zpi/wallet/get-portfolio/v1"

        payload = json.dumps({
            "addresses": [holder],
            "currency": "usd",
            "nftPriceType": "not_included"
        })

        headers = {
            'accept': 'application/json',
            'accept-language': 'en-AU,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://app.zerion.io',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'zerion-client-type': 'web',
            'user-agent': "PostmanRuntime/7.43.3",
            'zerion-client-version': '1.146.4',
            'zerion-wallet-provider': 'Watch Address',
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with self._lock:
                current_time = time.time()
                elapsed = current_time - self._last_request_time
                if elapsed < self._request_interval:
                    await asyncio.sleep(self._request_interval - elapsed)
                self._last_request_time = time.time()

            try:
                async with session.post(url, data=payload, headers=headers, proxy=proxy) as response:
                    response_text = await response.text()
                    print(response_text)
                    if response.status != 200:
                        raise aiohttp.ClientError(f"Unexpected status code: {response.status}")
                    data = await response.json()
                    balance = float(data["data"]["totalValue"])
                    print(f"Баланс {holder}: ${balance}")
                    return balance
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Network error for {holder}: {str(e)}")
                raise

async def main():
    e = EvmEngine()

    try:
        with open("./db/anti_duplicate.txt", "r") as f:
            holders = [line.strip() for line in f.readlines()]

        balances = await e.get_balances(holders)
        print("Final balances:", balances)

    except KeyboardInterrupt:
        print("❌ Программа прервана пользователем (Ctrl+C). Частичные результаты сохранены.")
        # Сохраняем частичные результаты, если они есть
        if 'balances' in locals():
            print(f"Частичные результаты: {balances}")
        return
    except Exception as e:
        print(f"❌ Ошибка в main: {str(e)}")
        if 'balances' in locals():
            print(f"Частичные результаты: {balances}")
        raise