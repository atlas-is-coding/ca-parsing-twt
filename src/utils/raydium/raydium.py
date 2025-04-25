import sys
from pathlib import Path

import aiohttp
import asyncio
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, Set, List
from dataclasses import field

from src.utils.raydium.models import PoolInfo, RaydiumResponse, TokenInfo, PoolStats, LpMintInfo

TRUSTED_TOKENS: list[str] = [
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "So11111111111111111111111111111111111111112",   # Wrapped SOL (wSOL)
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH (Wormhole)
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",   # mSOL
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj"   # stSOL
]


class Raydium:
    def _create_empty_pool_info(self, mint_address: str) -> PoolInfo:
        empty_token = TokenInfo(
            chainId=101,  # Solana mainnet
            address=mint_address,
            programId="",
            symbol="UNKNOWN",
            name="Unknown Token",
            decimals=0
        )
        empty_stats = PoolStats(
            volume=0,
            volumeQuote=0,
            volumeFee=0,
            apr=0,
            feeApr=0,
            priceMin=0,
            priceMax=0,
            rewardApr=[]
        )
        empty_lp_mint = LpMintInfo(
            chainId=101,
            address="",
            programId="",
            logoURI="",
            symbol="",
            name="",
            decimals=0
        )
        
        return PoolInfo(
            type="Unknown",
            programId="",
            id="",
            mintA=empty_token,
            mintB=empty_token,
            price=0,
            mintAmountA=0,
            mintAmountB=0,
            feeRate=0,
            tvl=0,
            openTime="0",
            day=empty_stats,
            week=empty_stats,
            month=empty_stats,
            lpMint=empty_lp_mint,
            lpPrice=0,
            lpAmount=0,
            liquidity_usd=0,
            is_rug=True,
            rewardDefaultPoolInfos=[],
            pooltype=[]
        )
        
    async def get_pool_info(self, mint_address: str) -> Optional[PoolInfo]:
        try:
            if mint_address in TRUSTED_TOKENS:
                pool_info = self._create_empty_pool_info(mint_address)
                pool_info.is_rug = False
                return pool_info
            
            params = {
                "mint1": mint_address,
                "poolType": "all",
                "poolSortField": "liquidity",
                "sortType": "desc",
                "pageSize": 1000,
                "page": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api-v3.raydium.io/pools/info/mint", params=params) as response:
                    if response.status != 200:
                        print(f"❌ Ошибка API Raydium: {response.status}")
                        return None
                        
                    data = await response.json()
                    raydium_response = RaydiumResponse(**data)
                
                    if not raydium_response.success:
                        return None

                    # Проверяем наличие пулов
                    if raydium_response.data["count"] == 0 or not raydium_response.data["data"]:
                        pool_info = self._create_empty_pool_info(mint_address)
                    else:
                        pool_data = raydium_response.data["data"][0]
                        pool_info = PoolInfo(**pool_data)
                        # Вычисляем ликвидность
                        if pool_info.lpPrice is not None and pool_info.lpAmount is not None:
                            pool_info.liquidity_usd = pool_info.lpPrice * pool_info.lpAmount
                            pool_info.is_rug = pool_info.liquidity_usd < 10_000
                        else:
                            pool_info.is_rug = True
                    
                    return pool_info
        except Exception as e:
            print(f"❌ Ошибка при получении информации о пуле: {str(e)}")
            return None