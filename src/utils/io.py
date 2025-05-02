import asyncio
import aiofiles
from typing import List, Optional
from pybloom_live import BloomFilter
import os

async def create_bloom_filter(filename: str, capacity: int = 10_000_000, error_rate: float = 0.01) -> BloomFilter:
    """
    Создает Bloom Filter из строк в файле.
    
    :param filename: Путь к файлу с дубликатами
    :param capacity: Ожидаемое количество строк в файле (для оптимизации размера фильтра)
    :param error_rate: Допустимая вероятность ложных срабатываний (например, 0.01 = 1%)
    :return: BloomFilter с загруженными строками
    """
    bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
    try:
        async with aiofiles.open(filename, mode='r', encoding='utf-8') as file:
            async for line in file:
                if line.strip():
                    bloom.add(line.strip())
    except FileNotFoundError:
        pass
    return bloom

async def filter_unique_holders_bloom(holders: List[str], filename: str, capacity: int = 10_000_000, error_rate: float = 0.01) -> List[str]:
    """
    Фильтрует список holders, оставляя только уникальные строки (не присутствующие в файле дубликатов).
    
    :param holders: Список строк для проверки
    :param filename: Путь к файлу с дубликатами
    :param capacity: Ожидаемое количество строк в файле
    :param error_rate: Вероятность ложных срабатываний
    :return: Список уникальных holders
    """
    bloom = await create_bloom_filter(filename, capacity, error_rate)
    unique_holders = [holder for holder in holders if holder not in bloom]
    return unique_holders

async def write_to_file(filename: str, lines: List[str], mode: str = 'w') -> None:
    async with aiofiles.open(filename, mode=mode, encoding='utf-8') as file:
        await file.write('\n'.join(lines) + '\n')


async def read_from_file(filename: str) -> List[str]:
    try:
        async with aiofiles.open(filename, mode='r', encoding='utf-8') as file:
            content = await file.read()
            # Strip empty lines and whitespace
            return [line.strip() for line in content.split('\n') if line.strip()]
    except FileNotFoundError:
        return []


async def is_line_in_file(filename: str, search_line: str, i = 0, t = 0) -> bool:
    try:
        lines = await read_from_file(filename)
        current = 1
        for line in lines:
            print(f"Проверка, есть ли строка в файле  [{i}/{t}]")
            if line.strip() == search_line.strip():
                return True
            
            current += 1
        return False
    except FileNotFoundError:
        return False
