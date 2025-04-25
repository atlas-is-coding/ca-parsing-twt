from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass
class TweetAnalysisResult:
    status: str
    selected_user: Optional[str]
    user_data: Optional[Dict]
    total_tweets: int
    unique_users: int

@dataclass
class TwitterUser:
    username: str
    is_dm_open: bool
    followers_count: int
    tweets_count: int = 0

@dataclass
class TwitterResponse:
    entries: List[Dict]
    has_more: bool
    next_cursor: Optional[str] = None