import aiohttp
import asyncio
import time
import os

from typing import List, Set

class EvmEngine:
    @staticmethod
    async def __make_request(url: str, headers: dict, retries: int = 5) -> dict:
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                    ) as response:
                        data = await response.json()

                        if data.get("data") and len(data["data"]) > 0:
                            return data
                    
                        await asyncio.sleep(0.2)
            except Exception as ex:
                print(f"❌ Ошибка {attempt + 1} попытки: {ex}")
                await asyncio.sleep(0.5)
                
        return {"result": None}


    async def get_holders(self, contract_address: str, chain: str) -> List[str]:
        page = 1
        total_pages = 99999999
        request_count = 0
        all_owners: Set[str] = set()
                
        start_time = time.time()
                
        while True:
            print(f"Обработка страницы {page}... | Всего страниц: {'неизвестно' if total_pages == 99999999 else total_pages}")
            if request_count > 250:
                print(f"Достигнут лимит запросов для {contract_address}, ожидание 5 минут")
                await asyncio.sleep(300)
                request_count = 0

            if page > total_pages:
                process_time = time.time() - start_time
                print(
                    f"Обработка {contract_address} завершена за {process_time:.2f}с, "
                    f"найдено {len(all_owners)} держателей"
                )
                break

            api_key = os.getenv("GRAPH_API_KEY")
            headers = {"Authorization": f"Bearer {api_key}"}
            data = await self.__make_request(f"https://token-api.thegraph.com/holders/evm/{contract_address}?network_id={chain}&order_by=desc&limit=1000&page={page}", headers)

            print(data)

            for account in data["data"]:
                all_owners.add(account["address"])

            if total_pages == 99999999:
                total_pages = data["pagination"]["total_pages"]

            request_count += 1
            page += 1

        return list(all_owners)
