from typing import List, Tuple
import os
import logging
from src.parsers.balance.chains import SolanaEngine, EvmEngine

logger = logging.getLogger(__name__)

class BalanceParser:
    def __init__(self):
        self.__solana_engine = SolanaEngine()
        self.__evm_engine = EvmEngine()

    async def get_balances(self, holders: List[str], network: str) -> List[Tuple[str, str]]:
        logger.info(f"Fetching balances for {len(holders)} holders on network: {network}")

        try:
            match network:
                case "sol":
                    balances = await self.__solana_engine.get_balances(holders)
                case "evm":
                    # Инициализируем EvmEngine перед запросами
                    await self.__evm_engine.initialize()
                    balances = await self.__evm_engine.get_balances(holders)
                case _:
                    logger.error(f"Неверная сеть: {network}")
                    balances = []
        except Exception as e:
            logger.error(f"Ошибка при получении балансов для сети {network}: {e}")
            balances = [(holder, "0") for holder in holders]

        # Фильтрация балансов по MIN_BALANCE_USD и MAX_BALANCE_USD
        min_balance = float(os.getenv("MIN_BALANCE_USD", "0"))
        max_balance = float(os.getenv("MAX_BALANCE_USD", float("inf")))
        balances = [
            balance for balance in balances
            if min_balance <= float(balance[1]) <= max_balance
        ]
        logger.info(f"Filtered balances: {len(balances)} wallets within range [{min_balance}, {max_balance}]")
        return balances