from typing import List
from enum import Enum
import aiohttp
import asyncio
import time
import os 

from src.utils import is_line_in_file, write_to_file, filter_unique_holders_bloom

from src.parsers.ca.chains import SolanaEngine, EvmEngine

class CAParser:
    def __init__(self):
        self.__solana_engine = SolanaEngine()
        self.__evm_engine = EvmEngine()
    
    async def get_holders(self, contract_address: str, contract_type: str) -> List[str]:
        print(f"Начинаю парсинг холдеров...")

        holders: List[str] = []

        match contract_type:
            case "sol":
                holders = await self.__solana_engine.get_holders(contract_address)
            case "mainnet":
                holders = await self.__evm_engine.get_holders(contract_address, "mainnet")
            case "bsc":
                holders = await self.__evm_engine.get_holders(contract_address, "bsc")
            case "base":
                holders = await self.__evm_engine.get_holders(contract_address, "base")
            case "arbitrum-one":
                holders = await self.__evm_engine.get_holders(contract_address, "arbitrum-one")
            case "optimism":
                holders = await self.__evm_engine.get_holders(contract_address, "optimism")
            case "matic":
                holders = await self.__evm_engine.get_holders(contract_address, "matic")
            case _:
                print(f"Такая сеть не поддерживается: {contract_type}")
                holders = []

        print(f"Всего холдеров: {len(holders)}")
        filename = os.path.join(os.getenv("DB_PATH"), os.getenv("ANTI_DUPLICATE_FILE"))
        holders = await filter_unique_holders_bloom(holders, filename)
        print(f"Всего уникальных холдеров: {len(holders)}")

        await write_to_file(os.path.join(os.getenv("DB_PATH"), os.getenv("ANTI_DUPLICATE_FILE")), holders, "a")

        return holders    

        