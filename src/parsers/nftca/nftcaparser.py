from typing import List
from enum import Enum
import aiohttp
import asyncio
import time
import os 

from src.utils import is_line_in_file, write_to_file

from src.parsers.nftca.chains import SolanaEngine, EvmEngine

class NftCAParser:
    def __init__(self):
        self.__solana_engine = SolanaEngine()
        self.__evm_engine = EvmEngine()
    
    async def get_holders(self, contract_address: str, contract_type: str) -> List[str]:
        print(f"Начинаю парсинг холдеров...")

        holders: List[str] = []

        match contract_type:
            case "sol":
                holders = await self.__solana_engine.get_holders(contract_address)
            case "eth":
                holders = await self.__evm_engine.get_holders(contract_address, "eth")
            case "bsc":
                holders = await self.__evm_engine.get_holders(contract_address, "bsc")
            case "base":
                holders = await self.__evm_engine.get_holders(contract_address, "base")
            case "arbitrum":
                holders = await self.__evm_engine.get_holders(contract_address, "arbitrum") 
            case "optimism":
                holders = await self.__evm_engine.get_holders(contract_address, "optimism")
            case "polygon":
                holders = await self.__evm_engine.get_holders(contract_address, "polygon")
            case _:
                print(f"Invalid contract type: {contract_type} | Unsupported contract chain")
                holders = []

        print(f"Всего холдеров: {len(holders)}")
        holders = [holder for holder in holders if not await is_line_in_file(os.path.join(os.getenv("DB_PATH"), os.getenv("ANTI_DUPLICATE_FILE")), holder)]
        print(f"Всего уникальных холдеров: {len(holders)}")

        await write_to_file(os.path.join(os.getenv("DB_PATH"), os.getenv("ANTI_DUPLICATE_FILE")), holders, "a")

        return holders