from playwright.async_api import async_playwright
import aiohttp
from typing import List, Tuple
import asyncio
import time
import json
import uuid
import random
from fake_useragent import UserAgent
import logging

from src.helpers.proxyManager import ProxyManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Асинхронная функция для получения куки
async def get_cookies():
    url = "https://app.zerion.io/0xf7b10d603907658f690da534e9b7dbc4dab3e2d6/overview"
    accept_button_selector = "#cookie-widget > div > div > div.rzbsmm6 > button.Button__ButtonElement-sc-sy8p3t-0.imKVVK._154dkog0._154dkog2"
    cookies_file = "cookies.json"

    # Попытка загрузить куки из файла
    async def load_cookies_from_file(filename=cookies_file):
        try:
            with open(filename, "r") as f:
                cookies = json.load(f)
                logger.info("Куки успешно загружены из файла")
                return cookies, UserAgent().random
        except FileNotFoundError:
            logger.info("Файл с куки не найден, будем получать новые")
            return None, None
        except Exception as e:
            logger.error(f"Ошибка при загрузке куки из файла: {e}")
            return None, None

    # Сохранение куки в файл
    async def save_cookies(cookies, filename=cookies_file):
        if cookies:
            try:
                with open(filename, "w") as f:
                    json.dump(cookies, f)
                logger.info(f"Куки сохранены в {filename}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении куки: {e}")

    # Проверка куки из файла
    cookies, user_agent = await load_cookies_from_file()
    if cookies:
        return cookies, user_agent

    # Получение новых куки через Playwright
    async def setup_browser(playwright):
        ua = UserAgent()
        user_agent = ua.random
        logger.info(f"Запуск браузера с User-Agent: {user_agent}")
        try:
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': random.randint(1280, 1920), 'height': random.randint(720, 1080)},
                locale='en-US',
                timezone_id='America/New_York',
                java_script_enabled=True,
                bypass_csp=True,
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = { runtime: {} };
            """)
            return browser, context, user_agent
        except Exception as e:
            logger.error(f"Ошибка при запуске браузера: {e}")
            raise

    async def wait_for_captcha_solution(page):
        logger.info("Проверяем наличие Cloudflare капчи...")
        max_wait_time = 60
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                if await page.locator("text=Verifying you are not a bot").count() > 0 or await page.locator("#challenge-running").count() > 0:
                    logger.info("Капча обнаружена. Ожидаем решения...")
                    await asyncio.sleep(5)
                else:
                    logger.info("Капча решена или отсутствует.")
                    return True
            except Exception as e:
                logger.error(f"Ошибка при проверке капчи: {e}")
                await asyncio.sleep(5)
        logger.error("Время ожидания капчи истекло.")
        return False

    async def wait_for_page_load(page):
        logger.info("Ожидаем полной загрузки страницы...")
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Страница полностью загружена.")
        except Exception as e:
            logger.error(f"Ошибка при ожидании загрузки страницы: {e}")
            raise

    logger.info("Запуск Playwright для получения куки...")
    async with async_playwright() as playwright:
        try:
            browser, context, user_agent = await setup_browser(playwright)
            page = await context.new_page()
            logger.info(f"Переход на страницу: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            if not await wait_for_captcha_solution(page):
                logger.error("Не удалось дождаться решения капчи.")
                return None, None
            await wait_for_page_load(page)
            logger.info("Ищем кнопку 'Accept'...")
            await page.wait_for_selector(accept_button_selector, timeout=10000)
            await page.click(accept_button_selector)
            logger.info("Кнопка 'Accept' нажата.")
            await asyncio.sleep(2)
            cookies = await context.cookies()
            logger.info("\nПолученные куки:")
            for cookie in cookies:
                logger.info(f"Name: {cookie['name']}, Value: {cookie['value']}, Domain: {cookie['domain']}")
            await save_cookies(cookies)
            return cookies, user_agent
        except Exception as e:
            logger.error(f"Произошла ошибка при получении куки: {e}")
            return None, None
        finally:
            if 'context' in locals():
                await context.close()
            if 'browser' in locals():
                await browser.close()

class EvmEngine:
    def __init__(self):
        self.max_concurrent_requests = 40
        self.api_rate_limit = self.max_concurrent_requests
        self._rate_limiter = asyncio.Semaphore(self.api_rate_limit)
        self._last_request_time = 0
        self._request_interval = 1.0 / self.api_rate_limit
        self._lock = asyncio.Lock()
        self.proxy_manager = ProxyManager()
        self.cookies = None
        self.user_agent = None
        self._remaining_requests = 100  # Начальное значение оставшихся запросов
        self._reset_time = 0  # Время сброса лимита
        self._backoff_time = 1.0  # Начальная задержка для экспоненциальной задержки

    async def initialize(self):
        logger.info("Инициализация EvmEngine...")
        cookies, user_agent = await get_cookies()
        if cookies:
            self.cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            self.user_agent = user_agent
            logger.info("Куки успешно инициализированы")
        else:
            logger.error("Не удалось получить куки. Используем пустые куки.")
            self.cookies = {}
            self.user_agent = UserAgent().random

    async def get_balances(self, holders: List[str]) -> List[Tuple[str, str]]:
        if self.cookies is None:
            logger.info("Куки не инициализированы, выполняем инициализацию")
            await self.initialize()

        balances: List[Tuple[str, str]] = []
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        total_holders = len(holders)
        processed_count = 0

        async def process_holder(holder: str) -> Tuple[str, str]:
            nonlocal processed_count
            async with semaphore:
                try:
                    result = await self.__get_balance(holder)
                    processed_count += 1
                    logger.info(f"Processed {processed_count} of {total_holders} wallets")
                    return (holder, str(result))
                except Exception as e:
                    processed_count += 1
                    logger.error(f"Error processing wallet {holder}: {str(e)}")
                    return (holder, "0")

        tasks = [process_holder(holder) for holder in holders]

        try:
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    balances.append(result)
                except asyncio.CancelledError:
                    logger.info("Задача отменена. Возвращаю частичные результаты...")
                    return balances
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.error(f"Сетевая ошибка в задаче: {str(e)}. Продолжаю с частичными результатами...")
                    continue
                except Exception as e:
                    logger.error(f"Неожиданная ошибка в задаче: {str(e)}. Продолжаю...")
                    continue
        except KeyboardInterrupt:
            logger.info("Процесс прерван пользователем (Ctrl+C). Возвращаю частичные результаты...")
            for task in tasks:
                task.cancel()
            return balances
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Сетевая ошибка: {str(e)}. Возвращаю частичные результаты...")
            return balances

        return balances

    async def __get_balance(self, holder: str) -> float:
        proxy = self.proxy_manager.get_proxy()
        url = f"https://api.zerion.io/v1/wallets/{holder}/portfolio?filter[positions]=no_filter¤cy=usd"

        headers = {
            "accept": "application/json",
            "authorization": f"Basic emtfZGV2X2M1MTAyNzIzZmVmYzQ2OGViZmEwNzRkNDA2NDZhZmVlOg=="
        }

        max_retries = 3
        for attempt in range(max_retries):
            async with self._rate_limiter:
                async with self._lock:
                    current_time = time.time()
                    if current_time >= self._reset_time and self._remaining_requests == 0:
                        self._remaining_requests = 100
                        self._backoff_time = 1.0
                        logger.info("Сброс лимита запросов")

                    if self._remaining_requests <= 0:
                        wait_time = self._reset_time - current_time
                        if wait_time > 0:
                            logger.info(f"Достигнут лимит запросов. Ожидание {wait_time:.2f} секунд")
                            await asyncio.sleep(wait_time)

                    elapsed = current_time - self._last_request_time
                    if elapsed < self._request_interval:
                        await asyncio.sleep(self._request_interval - elapsed)
                    self._last_request_time = time.time()

                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                        async with session.get(url, headers=headers, proxy=proxy) as response:
                            if 'x-ratelimit-remaining' in response.headers:
                                self._remaining_requests = int(response.headers['x-ratelimit-remaining'])
                            if 'x-ratelimit-reset' in response.headers:
                                self._reset_time = float(response.headers['x-ratelimit-reset'])

                            if response.status == 429:
                                wait_time = self._backoff_time
                                if 'retry-after' in response.headers:
                                    wait_time = float(response.headers['retry-after'])
                                logger.warning(f"Rate limit превышен для {holder}. Ожидание {wait_time} секунд")
                                await asyncio.sleep(wait_time)
                                self._backoff_time = min(self._backoff_time * 2, 60)
                                continue

                            response.status = 401
                            if response.status != 200:
                                logger.error(f"Unexpected status code for {holder}: {response.status}")
                                return 0.0

                            try:
                                data = await response.json()
                                logger.info(f"Raw API response for {holder}: {data}")
                                total_positions = data.get("data", {}).get("attributes", {}).get("total", {}).get(
                                    "positions")
                                if total_positions is None or total_positions == "None":
                                    logger.warning(f"No balance data for {holder}, returning 0")
                                    return 0.0
                                balance = float(total_positions)
                                logger.info(f"Баланс {holder}: ${balance}")
                                self._backoff_time = 1.0
                                return balance
                            except (KeyError, ValueError) as e:
                                logger.error(f"Error parsing response for {holder}: {str(e)}")
                                return 0.0

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.error(f"Network error for {holder} (попытка {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt == max_retries - 1:
                        return 0.0
                    await asyncio.sleep(self._backoff_time)
                    self._backoff_time = min(self._backoff_time * 2, 60)

        return 0.0