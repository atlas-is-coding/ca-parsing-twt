from typing import List, Tuple
import os

from src.parsers.balance.chains import SolanaEngine, EvmEngine

class BalanceParser:
    def __init__(self):
        self.__solana_engine = SolanaEngine()
        self.__evm_engine = EvmEngine()

    async def get_balances(self, holders: List[str], network: str) -> List[Tuple[str, str]]:
        balances: List[Tuple[str, str]] = []

        match network:
            case "sol":
                balances = await self.__solana_engine.get_balances(holders)
            case "evm":
                balances = await self.__evm_engine.get_balances(holders)
            case _:
                print(f"Неверная сеть: {network}")
                balances = []

        balances = [balance for balance in balances if float(os.getenv("MIN_BALANCE_USD")) <= float(balance[1]) <= float(os.getenv("MAX_BALANCE_USD"))]
        return balances