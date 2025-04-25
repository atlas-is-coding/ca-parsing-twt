import aiohttp
import asyncio
import time
import os

from typing import List, Set

from moralis import evm_api

class EvmEngine:
    async def get_holders(self, contract_address: str, chain: str) -> List[str]:
        cursor = None
        page = 1

        holders = []

        while True:
            params = {
                "chain": chain,
                "format": "decimal",
                "limit": 100,
                "address": contract_address
            }
            
            if cursor is not None:
                params["cursor"] = cursor

            result = evm_api.nft.get_nft_owners(
                api_key=os.getenv("MORALIS_API_KEY"),
                params=params,
            )

            data = result.get("result")
            if data is None:
                break
            
            owners = [item.get("owner_of") for item in data]
            holders.extend(owners)

            cursor = result.get("cursor")
            if cursor is None:
                break

            page += 1

            print(f"Обработано {len(holders)} держателей для {contract_address}")

        return holders
