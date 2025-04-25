import aiohttp
import asyncio
import time
import os
import json

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
                            "method": "getAssetsByGroup",  
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
                
                        if data.get("result") and data["result"]["total"] == 1000:
                            return data
                    
                        await asyncio.sleep(0.2)
            except Exception as ex:
                print(f"❌ Ошибка попытки {attempt + 1}: {ex}")
                await asyncio.sleep(0.5)
                
        return {"result": None}


    async def get_holders(self, contract_address: str) -> List[str]:
        page = 1
        asset_list = []

        start_time = time.time()
                
        while True:
            params = {
                "groupKey": "collection",
                "groupValue": contract_address,
                "page": page,
                "limit": 1000,
            }
                    
            data = await self.__make_request(params=params)
                    
            if not data.get("result"):
                process_time = time.time() - start_time
                print(
                    f"Обработка {contract_address} завершена за {process_time:.2f}с, "
                    f"найдено {len(asset_list)} держателей"
                )
                break

            owners = [item["ownership"]["owner"] for item in data["result"].get("items", [])]

            asset_list.extend(owners)
            
            page += 1

            print(f"Обработано {len(asset_list)} держателей для {contract_address}")
        return asset_list