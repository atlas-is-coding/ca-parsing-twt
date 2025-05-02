from playwright.async_api import async_playwright
import aiohttp
from typing import List, Tuple
import asyncio
import time
import json
import uuid
import random
import platform
from fake_useragent import UserAgent
import logging

from src.helpers.proxyManager import ProxyManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Функция для генерации мобильного User-Agent
def get_mobile_user_agent():
    with open("user_agents.txt", "r") as ua:
      return random.choice([line.strip() for line in ua.readlines()])

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
        # Список методов парсинга
        parse_methods = [
            self.zerion_api_parse,
            self.zerion_general_parse
        ]
        method_index = 0  # Начнем с первого метода (zerion_api_parse)
        attempt = 0

        while True:
            current_method = parse_methods[method_index]
            method_name = current_method.__name__
            logger.info(f"Попытка парсинга с помощью {method_name} (попытка {attempt + 1})")

            try:
                balances = await current_method(holders)
                logger.info(f"Успешно получены балансы с помощью {method_name}")
                # Проверяем, что данные содержат хотя бы один ненулевой баланс
                if any(balance != "0" for _, balance in balances):
                    return balances
                else:
                    logger.warning(f"Получены нулевые балансы с {method_name}. Пробуем следующий метод.")
                    method_index = (method_index + 1) % len(parse_methods)
                    attempt += 1
                    wait_time = min(2 ** min(attempt, 10), 60)
                    logger.info(f"Ожидание {wait_time} секунд перед следующей попыткой...")
                    await asyncio.sleep(wait_time)

            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    logger.warning(
                        f"Ошибка 429 (Rate Limit) при использовании {method_name}. Переключаемся на следующий метод.")
                    method_index = (method_index + 1) % len(parse_methods)
                    attempt += 1
                    wait_time = min(2 ** min(attempt, 10), 60)
                    # Проверяем headers на None и наличие retry-after
                    if hasattr(e, 'headers') and e.headers is not None and 'retry-after' in e.headers:
                        try:
                            retry_after = float(e.headers.get('retry-after', wait_time))
                            wait_time = max(wait_time, retry_after)
                        except ValueError:
                            logger.warning("Невалидное значение retry-after, использую стандартную задержку")
                    logger.info(f"Ожидание {wait_time} секунд перед следующей попыткой...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Ошибка HTTP при использовании {method_name}: {str(e)}")
                    method_index = (method_index + 1) % len(parse_methods)
                    attempt += 1
                    wait_time = min(2 ** min(attempt, 10), 60)
                    logger.info(f"Ожидание {wait_time} секунд перед следующей попыткой...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Неожиданная ошибка при использовании {method_name}: {type(e).__name__}: {str(e)}")
                method_index = (method_index + 1) % len(parse_methods)
                attempt += 1
                wait_time = min(2 ** min(attempt, 10), 60)
                logger.info(f"Ожидание {wait_time} секунд перед следующей попыткой...")
                await asyncio.sleep(wait_time)

    # ========================================================================
    async def zerion_api_parse(self, holders: List[str]) -> List[Tuple[str, str]]:
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
                    result = await self.__zerion_api_get_balance(holder)
                    processed_count += 1
                    logger.info(f"Processed {processed_count} of {total_holders} wallets")
                    return (holder, str(result))
                except aiohttp.ClientResponseError as e:
                    processed_count += 1
                    if e.status == 429:
                        logger.warning(f"Rate limit error for {holder}. Raising to switch method.")
                        raise  # Передаем 429 наверх
                    logger.error(f"HTTP error processing wallet {holder}: {str(e)}")
                    return (holder, "0")
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
                except aiohttp.ClientResponseError as e:
                    if e.status == 429:
                        logger.warning("Rate limit error in zerion_api_parse. Raising to get_balances.")
                        raise  # Передаем 429 наверх
                    logger.error(f"HTTP error in task: {str(e)}")
                    continue
                except asyncio.CancelledError:
                    logger.info("Задача отменена. Возвращаю частичные результаты...")
                    return balances
                except Exception as e:
                    logger.error(f"Неожиданная ошибка в задаче: {str(e)}")
                    continue
        except KeyboardInterrupt:
            logger.info("Процесс прерван пользователем (Ctrl+C). Возвращаю частичные результаты...")
            for task in tasks:
                task.cancel()
            return balances

        return balances

    async def __zerion_api_get_balance(self, holder: str) -> float:
        proxy = self.proxy_manager.get_proxy()
        url = f"https://api.zerion.io/v1/wallets/{holder}/portfolio?filter[positions]=no_filter&currency=usd"

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
                                logger.warning(f"Rate limit превышен для {holder}. Передача ошибки наверх.")
                                raise aiohttp.ClientResponseError(
                                    status=429,
                                    message="Rate limit exceeded",
                                    headers=response.headers,  # Передаем заголовки ответа
                                    request_info=response.request_info,
                                    history=response.history
                                )

                            if platform == "Windows":
                                response.status = 401
                            if response.status != 200:
                                logger.error(f"Unexpected status code for {holder}: {response.status}")
                                raise aiohttp.ClientResponseError(
                                    status=response.status,
                                    message=f"Unexpected status code: {response.status}",
                                    headers=response.headers,
                                    request_info=response.request_info,
                                    history=response.history
                                )
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
                        raise  # Передаем сетевые ошибки наверх
                    await asyncio.sleep(self._backoff_time)
                    self._backoff_time = min(self._backoff_time * 2, 60)

        raise Exception(f"Failed to get balance for {holder} after {max_retries} attempts")
    # ========================================================================

    async def zerion_general_parse(self, holders: List[str]) -> List[Tuple[str, str]]:
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
                    result = await self.__zerion_general_get_balance(holder)
                    processed_count += 1
                    logger.info(f"Processed {processed_count} of {total_holders} wallets")
                    return (holder, str(result))
                except aiohttp.ClientResponseError as e:
                    processed_count += 1
                    if e.status == 429:
                        logger.warning(f"Rate limit error for {holder}. Raising to switch method.")
                        raise  # Передаем 429 наверх
                    logger.error(f"HTTP error processing wallet {holder}: {str(e)}")
                    return (holder, "0")
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
                except aiohttp.ClientResponseError as e:
                    if e.status == 429:
                        logger.warning("Rate limit error in zerion_general_parse. Raising to get_balances.")
                        raise  # Передаем 429 наверх
                    logger.error(f"HTTP error in task: {str(e)}")
                    continue
                except asyncio.CancelledError:
                    logger.info("Задача отменена. Возвращаю частичные результаты...")
                    return balances
                except Exception as e:
                    logger.error(f"Неожиданная ошибка в задаче: {str(e)}")
                    continue
        except KeyboardInterrupt:
            logger.info("Процесс прерван пользователем (Ctrl+C). Возвращаю частичные результаты...")
            for task in tasks:
                task.cancel()
            return balances

        return balances

    async def __zerion_general_get_balance(self, holder: str) -> float:
        proxy = self.proxy_manager.get_proxy()
        url = f"https://zpi.zerion.io/wallet/get-portfolio/v1"

        payload = json.dumps({
            "addresses": [holder],
            "currency": "usd",
            "nftPriceType": "not_included"
        })

        headers = {
            'accept': 'application/json',
            'accept-language': 'en-AU,en;q=0.9',
            'content-type': 'application/json',
            'user-agent': get_mobile_user_agent(),
            'origin': 'https://app.zerion.io',
            'priority': 'u=1, i',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-request-id': str(uuid.uuid4()),
            'zerion-client-type': 'web',
            'zerion-client-version': '1.146.4',
            'zerion-session-id': str(uuid.uuid4()),
            'zerion-wallet-provider': 'Watch Address'
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
                        async with session.post(url, headers=headers, proxy=proxy, data=payload) as response:
                            if 'x-ratelimit-remaining' in response.headers:
                                self._remaining_requests = int(response.headers['x-ratelimit-remaining'])
                            if 'x-ratelimit-reset' in response.headers:
                                self._reset_time = float(response.headers['x-ratelimit-reset'])

                            if response.status == 429:
                                logger.warning(f"Rate limit превышен для {holder}. Передача ошибки наверх.")
                                raise aiohttp.ClientResponseError(
                                    status=429,
                                    message="Rate limit exceeded",
                                    headers=response.headers,  # Передаем заголовки ответа
                                    request_info=response.request_info,
                                    history=response.history
                                )

                            if platform == "Windows":
                                response.status = 401
                            if response.status != 200:
                                logger.error(f"Unexpected status code for {holder}: {response.status}")
                                raise aiohttp.ClientResponseError(
                                    status=response.status,
                                    message=f"Unexpected status code: {response.status}",
                                    headers=response.headers,
                                    request_info=response.request_info,
                                    history=response.history
                                )
                            try:
                                data = await response.json()
                                logger.info(f"Raw API response for {holder}: {data}")
                                total_positions = data.get("data", {}).get("totalValue", 0)
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
                        raise  # Передаем сетевые ошибки наверх
                    await asyncio.sleep(self._backoff_time)
                    self._backoff_time = min(self._backoff_time * 2, 60)

        raise Exception(f"Failed to get balance for {holder} after {max_retries} attempts")


async def main():
    evm = EvmEngine()

    with open("db/anti_duplicate.txt", "r") as f:
        lines = [line.strip() for line in f.readlines() if line.startswith("0x")]
        balances = await evm.get_balances(lines)

        print(balances[:5], len(balances))

if __name__ == '__main__':
    asyncio.run(main())