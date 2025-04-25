import aiohttp
import asyncio
import time
import os

from typing import List, Set
from src.helpers.rpcManager import RpcManager

class SolanaEngine:
    def __init__(self):
        self.rpc_manager = RpcManager()

    @RpcManager.with_rpc_rotation
    async def __make_request(self, rpc_url: str, params: dict, retries: int = 5) -> dict:
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        rpc_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": "helius",
                            "method": "getTokenAccounts",
                            "params": params,
                        },
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        data = await response.json()
                        if response.status == 429:
                            if data["error"]["message"] == "max usage reached":
                                print(f"❌ Ошибка. Лимит RPC достигнут, обновите RPC | {rpc_url}")

                                rpc_url = await self.rpc_manager.get_next_rpc()
                            else:
                                print(response.text)
                        
                        if data.get("result") and len(data["result"]["token_accounts"]) > 0:
                            return data
                        await asyncio.sleep(0.2)
            except Exception as ex:
                print(f"❌ Ошибка попытки {attempt + 1}: {ex}")
                await asyncio.sleep(0.5)
        return {"result": None}

    async def _fetch_page(self, contract_address: str, cursor: str | None, semaphore: asyncio.Semaphore) -> tuple[Set[str], str | None]:
        async with semaphore:
            params = {
                "limit": 1000,
                "mint": contract_address,
                "options": {"showZeroBalance": True},
            }
            if cursor is not None:
                params["cursor"] = cursor

            data = await self.__make_request(params=params)
            owners = set()
            next_cursor = None

            if data.get("result"):
                for account in data["result"]["token_accounts"]:
                    owners.add(account["owner"])
                next_cursor = data["result"].get("cursor")

            return owners, next_cursor

    async def get_holders(self, contract_address: str, max_concurrency: int = 5) -> List[str]:
        all_owners: Set[str] = set()
        cursors: List[str | None] = [None]  # Начальный курсор
        request_count = 0
        start_time = time.time()

        # Создаем семафор для ограничения параллельных запросов
        semaphore = asyncio.Semaphore(max_concurrency)

        while cursors:
            if request_count > 250:
                print(f"Достигнут лимит запросов для {contract_address}, ожидание 5 минут")
                await asyncio.sleep(300)
                request_count = 0

            # Создаем задачи для текущего набора курсоров
            tasks = [
                self._fetch_page(contract_address, cursor, semaphore)
                for cursor in cursors
            ]
            cursors = []  # Очищаем список курсоров

            # Выполняем задачи с учетом семафора
            results = await asyncio.gather(*tasks, return_exceptions=True)
            request_count += len(tasks)

            # Обрабатываем результаты
            for result in results:
                if isinstance(result, Exception):
                    print(f"❌ Ошибка в задаче: {result}")
                    continue

                owners, next_cursor = result
                all_owners.update(owners)
                if next_cursor:
                    cursors.append(next_cursor)

        process_time = time.time() - start_time
        print(
            f"Обработка {contract_address} завершена за {process_time:.2f}с, "
            f"найдено {len(all_owners)} держателей"
        )
        return list(all_owners)