import os
import asyncio
import aiohttp
import time
from typing import List, Tuple, Dict, Optional
from decimal import Decimal
from dataclasses import dataclass, field
import json
import logging

from src.utils import sort_token_accounts, Raydium
from src.helpers.rpcManager import RpcManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WalletBalance:
    holder: str
    sol_balance: dict
    tokens: List[dict] = field(default_factory=list)
    total_usd_value: Decimal = Decimal(0)

    def calculate_total_value(self) -> None:
        self.total_usd_value = sum(
            (token["usd_value"] or Decimal(0))
            for token in [self.sol_balance, *self.tokens]
            if token["usd_price"] is not None and token["usd_price"] > 0
        )

    @property
    def formatted_total_value(self) -> str:
        return f"{self.total_usd_value:.2f}"

class SolanaEngine:
    def __init__(self):
        self.raydium = Raydium()
        self.max_concurrent_requests = 40
        self.api_rate_limit = 5
        self._rate_limiter = asyncio.Semaphore(self.api_rate_limit)
        self._last_request_time = 0
        self._request_interval = 1.0 / self.api_rate_limit
        self._lock = asyncio.Lock()
        self.rpc_manager = RpcManager()

    async def get_balances(self, holders: List[str]) -> List[Tuple[str, str]]:
        balances: List[Tuple[str, str]] = []
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        total_holders = len(holders)
        processed_count = 0

        async def process_holder(holder: str) -> Optional[Tuple[str, str]]:
            nonlocal processed_count
            async with semaphore:
                # Проверяем отмену перед началом обработки
                if asyncio.current_task().cancelled():
                    logger.info(f"Задача для {holder} отменена до начала")
                    return None
                try:
                    result: WalletBalance = await self.__get_balance(holder)
                    processed_count += 1
                    logger.info(f"Анализирую кошельки [{processed_count}/{total_holders}]")
                    return (result.holder, result.formatted_total_value)
                except asyncio.CancelledError:
                    logger.info(f"Задача для {holder} отменена во время обработки")
                    raise
                except Exception as e:
                    processed_count += 1
                    logger.warning(f"❌ Ошибка при анализе кошелька {holder}: {str(e)}")
                    return (holder, "0")

        tasks = []
        for holder in holders:
            # Проверяем отмену перед созданием задачи
            if asyncio.current_task().cancelled():
                logger.info("❌ Задача get_balances отменена перед созданием новых задач")
                break
            task = asyncio.create_task(process_holder(holder), name=f"process_holder_{holder}")
            tasks.append(task)

        try:
            for future in asyncio.as_completed(tasks):
                # Проверяем отмену перед обработкой результата
                if asyncio.current_task().cancelled():
                    logger.info("❌ Задача get_balances отменена. Отменяю оставшиеся задачи...")
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    return balances
                try:
                    result = await future
                    if result:
                        balances.append(result)
                except asyncio.CancelledError:
                    logger.info("❌ Задача get_balances отменена. Отменяю оставшиеся задачи...")
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    return balances
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"❌ Сетевая ошибка в задаче: {str(e)}. Продолжаю...")
                    continue
                except Exception as e:
                    logger.warning(f"❌ Неожиданная ошибка в задаче: {str(e)}. Продолжаю...")
                    continue
        except asyncio.CancelledError:
            logger.info("❌ Задача get_balances отменена (внешний уровень). Отменяю оставшиеся задачи...")
            for task in tasks:
                if not task.done():
                    task.cancel()
            return balances
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.info(f"❌ Сетевая ошибка: {str(e)}. Возвращаю частичные результаты...")
            return balances

        logger.info(f"Завершено: обработано {processed_count}/{total_holders} кошельков")
        return balances

    async def __get_balance(self, holder: str) -> WalletBalance:
        MAX_RETRIES = 2
        RETRY_DELAY = 2

        for attempt in range(MAX_RETRIES):
            # Проверяем отмену перед началом попытки
            if asyncio.current_task().cancelled():
                logger.info(f"Задача для {holder} отменена перед попыткой {attempt + 1}")
                raise asyncio.CancelledError()
            try:
                token_accounts = await self._get_wallet_tokens(holder=holder)
                if not token_accounts:
                    empty_sol = {
                        "mint": "So11111111111111111111111111111111111111112",
                        "symbol": "SOL",
                        "name": "Solana",
                        "decimals": 9,
                        "amount": Decimal(0),
                        "token_accounts": [],
                        "usd_price": None,
                        "usd_value": None
                    }
                    wallet_balance = WalletBalance(
                        holder=holder,
                        sol_balance=empty_sol,
                        tokens=[]
                    )
                    wallet_balance.calculate_total_value()
                    return wallet_balance

                sol_data = next(
                    (t for t in token_accounts if t["mint"] == "So11111111111111111111111111111111111111112"), None)
                if sol_data:
                    amount = Decimal(sol_data["amount"]) / Decimal(10 ** sol_data["decimals"])
                    sol_balance = {
                        "mint": sol_data["mint"],
                        "symbol": sol_data["symbol"],
                        "name": sol_data["name"],
                        "decimals": sol_data["decimals"],
                        "amount": amount,
                        "token_accounts": sol_data["token_accounts"],
                        "usd_price": sol_data["usd_price"],
                        "usd_value": sol_data["usd_value"]
                    }
                    token_accounts = [t for t in token_accounts if
                                      t["mint"] != "So11111111111111111111111111111111111111112"]

                    async def process_token(token_account):
                        # Проверяем отмену перед обработкой токена
                        if asyncio.current_task().cancelled():
                            logger.info(f"Задача для токена {token_account['mint']} отменена")
                            raise asyncio.CancelledError()
                        try:
                            amount = Decimal(token_account["amount"]) / Decimal(10 ** token_account["decimals"])
                            token = {
                                "mint": token_account["mint"],
                                "symbol": token_account["symbol"],
                                "name": token_account["name"],
                                "decimals": token_account["decimals"],
                                "amount": amount,
                                "token_accounts": token_account["token_accounts"],
                                "usd_price": token_account["usd_price"],
                                "usd_value": token_account["usd_value"]
                            }
                            if token["mint"] != "So11111111111111111111111111111111111111112":
                                pool_info = await self.raydium.get_pool_info(token_account["mint"])
                                if pool_info and not pool_info.is_rug:
                                    return token
                                return None
                            return None
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.warning(f"❌ Ошибка при проверке Raydium для {token_account['symbol']}: {str(e)}")
                            return None

                    token_semaphore = asyncio.Semaphore(5)
                    async def safe_process_token(token_account):
                        async with token_semaphore:
                            return await process_token(token_account)

                    token_tasks = [safe_process_token(token) for token in token_accounts]
                    token_results = await asyncio.gather(*token_tasks, return_exceptions=False)  # Убрали return_exceptions
                    processed_tokens = [t for t in token_results if t is not None]
                else:
                    processed_tokens = []
            except asyncio.CancelledError:
                logger.info(f"Задача для {holder} отменена на попытке {attempt + 1}")
                raise
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Попытка {attempt + 1} для {holder} не удалась: {str(e)}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                logger.warning(f"Не смог проанализировать кошелек {holder} после {MAX_RETRIES} попыток: {str(e)}")
                sol_balance = {
                    "mint": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                    "name": "Solana",
                    "decimals": 9,
                    "amount": Decimal(0),
                    "token_accounts": [],
                    "usd_price": None,
                    "usd_value": None
                }
                wallet_balance = WalletBalance(
                    holder=holder,
                    sol_balance=sol_balance,
                    tokens=[]
                )
                wallet_balance.calculate_total_value()
                return wallet_balance
            break

        if not sol_data:
            sol_balance = {
                "mint": "So11111111111111111111111111111111111111112",
                "symbol": "SOL",
                "name": "Solana",
                "decimals": 9,
                "amount": Decimal(0),
                "token_accounts": [],
                "usd_price": None,
                "usd_value": None
            }
        wallet_balance = WalletBalance(
            holder=holder,
            sol_balance=sol_balance,
            tokens=processed_tokens
        )
        wallet_balance.calculate_total_value()
        logger.info(f"Баланс {holder}: {wallet_balance.formatted_total_value}")
        return wallet_balance

    @RpcManager.with_rpc_rotation
    async def _get_wallet_tokens(self, rpc_url: str, holder: str) -> List[Dict]:
        if not rpc_url:
            logger.error("❌ Ошибка: RPC URL не предоставлен")
            return []

        async with self._lock:
            current_time = time.time()
            elapsed = current_time - self._last_request_time
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
            self._last_request_time = time.time()

        # Проверяем отмену перед запросом
        if asyncio.current_task().cancelled():
            logger.info(f"Задача для {holder} отменена перед HTTP-запросом")
            raise asyncio.CancelledError()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                        rpc_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": "my-id",
                            "method": "searchAssets",
                            "params": {
                                "ownerAddress": holder,
                                "tokenType": "fungible",
                                "displayOptions": {
                                    "showNativeBalance": True,
                                },
                            }
                        }
                ) as response:
                    if response.status != 200:
                        error_msg = f"❌ Ошибка при парсинге монет для {holder}: {await response.text()}"
                        logger.error(error_msg)
                        return []
                    try:
                        data = await response.json()
                    except Exception as e:
                        logger.error(f"❌ Ошибка при парсинге JSON для {holder}: {str(e)}")
                        return []

                    result = data.get("result", {})
                    native_balance = result.get("nativeBalance")
                    if native_balance:
                        sol_data = {
                            "mint": "So11111111111111111111111111111111111111112",
                            "symbol": "SOL",
                            "name": "Solana",
                            "decimals": 9,
                            "amount": native_balance.get("lamports", 0),
                            "token_accounts": [],
                            "usd_price": native_balance.get("price_per_sol"),
                            "usd_value": native_balance.get("total_price")
                        }
                        tokens = [sol_data]
                    else:
                        tokens = []

                    for asset in result.get("items", []):
                        if "token_info" not in asset:
                            continue
                        token_info = asset["token_info"]
                        price_info = None
                        if "price_info" in token_info:
                            price_data = token_info["price_info"]
                            price_info = {
                                "price_per_token": price_data.get("price_per_token"),
                                "total_price": price_data.get("total_price"),
                                "currency": price_data.get("currency")
                            }
                        token_data = {
                            "mint": asset["id"],
                            "symbol": token_info.get("symbol", "UNKNOWN"),
                            "name": asset.get("content", {}).get("metadata", {}).get("name", "Unknown Token"),
                            "decimals": token_info.get("decimals", 0),
                            "amount": token_info.get("balance", 0),
                            "token_accounts": [
                                {
                                    "address": acc["address"],
                                    "balance": acc["balance"]
                                } for acc in token_info.get("token_accounts", [])
                            ],
                            "usd_price": price_info["price_per_token"] if price_info else None,
                            "usd_value": price_info["total_price"] if price_info else None
                        }
                        tokens.append(token_data)
                    sorted_tokens = sort_token_accounts(tokens)
                    return sorted_tokens
        except asyncio.CancelledError:
            logger.info(f"Задача для {holder} отменена во время HTTP-запроса")
            raise
        except asyncio.TimeoutError:
            logger.error(f"Ожидание превышено для {holder}")
            return []
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка для {holder}: {str(e)}")
            return []