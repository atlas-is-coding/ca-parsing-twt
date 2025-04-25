from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime

@dataclass
class TokenInfo:
    """Информация о токене"""
    chainId: int
    address: str
    programId: str
    symbol: str
    name: str
    decimals: int
    logoURI: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    extensions: dict = field(default_factory=dict)

@dataclass
class PoolStats:
    """Статистика пула"""
    volume: float
    volumeQuote: float
    volumeFee: float
    apr: float
    feeApr: float
    priceMin: float
    priceMax: float
    rewardApr: List[float]

@dataclass
class LpMintInfo:
    """Информация о LP токене"""
    chainId: int
    address: str
    programId: str
    logoURI: str
    symbol: str
    name: str
    decimals: int
    tags: List[str] = field(default_factory=list)
    extensions: dict = field(default_factory=dict)

@dataclass
class PoolInfo:
    """Информация о пуле ликвидности"""
    type: str
    programId: str
    id: str
    mintA: TokenInfo
    mintB: TokenInfo
    price: float
    mintAmountA: float
    mintAmountB: float
    feeRate: float
    tvl: float
    openTime: str
    day: PoolStats
    week: PoolStats
    month: PoolStats
    lpMint: Optional[LpMintInfo] = None
    lpPrice: Optional[float] = None
    lpAmount: Optional[float] = None
    liquidity_usd: Optional[float] = None
    is_rug: bool = False
    last_updated: datetime = field(default_factory=datetime.now)
    pooltype: List[str] = field(default_factory=list)
    rewardDefaultPoolInfos: List[Any] = field(default_factory=list)
    rewardDefaultInfos: List[Any] = field(default_factory=list)
    farmUpcomingCount: int = 0
    farmOngoingCount: int = 0
    farmFinishedCount: int = 0
    marketId: Optional[str] = None
    burnPercent: Optional[int] = None
    config: Optional[dict] = field(default_factory=dict)

@dataclass
class RaydiumResponse:
    """Ответ от Raydium API"""
    id: str
    success: bool
    data: dict