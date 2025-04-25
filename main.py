import asyncio
import os
import logging

from src.utils import async_init_project, write_to_file, read_from_file, is_line_in_file
from src.parsers.ca import CAParser
from src.parsers.balance import BalanceParser
from src.bot import bot, dp
from src.parsers.nftca import NftCAParser
from typing import List, Tuple

from dotenv import load_dotenv

load_dotenv()

async def main():
   await async_init_project()
   
   # # Configure logging
   logging.basicConfig(level=logging.INFO)
   logging.info("Запускаю бота...")
    
   # # Start the Telegram bot
   await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())