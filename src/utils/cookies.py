from playwright.sync_api import sync_playwright
import time
import random
from fake_useragent import UserAgent
import os

def setup_browser(playwright):
    # Генерируем случайный User-Agent
    ua = UserAgent()
    user_agent = ua.random

    # Запускаем браузер с настройками для антидетекта
    browser = playwright.chromium.launch(
        headless=False,  # Браузер видимый, чтобы пользователь мог решить капчу
        args=[
            '--disable-blink-features=AutomationControlled',  # Отключаем индикаторы автоматизации
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ]
    )

    # Создаем новый контекст браузера с кастомными настройками
    context = browser.new_context(
        user_agent=user_agent,
        viewport={'width': random.randint(1280, 1920), 'height': random.randint(720, 1080)},  # Случайный размер окна
        locale='en-US',
        timezone_id='America/New_York',  # Случайная временная зона
        java_script_enabled=True,
        bypass_csp=True,
    )

    # Дополнительные настройки для антидетекта
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """)

    return browser, context

def wait_for_captcha_solution(page):
    print("Проверяем наличие Cloudflare капчи...")
    while True:
        # Проверяем наличие капчи по селектору или тексту
        if page.locator("text=Verifying you are not a bot").count() > 0 or page.locator("#challenge-running").count() > 0:
            print("Капча обнаружена. Пожалуйста, решите капчу в браузере.")
            time.sleep(5)  # Ждем 5 секунд перед следующей проверкой
        else:
            print("Капча решена или отсутствует.")
            break

def get_cookies():
    url = "https://app.zerion.io/0xf7b10d603907658f690da534e9b7dbc4dab3e2d6/overview"

    with sync_playwright() as playwright:
        browser, context = setup_browser(playwright)
        page = context.new_page()

        try:
            # Переходим на сайт
            page.goto(url, wait_until="domcontentloaded")

            # Ждем решения капчи, если она есть
            wait_for_captcha_solution(page)

            # Ждем загрузки страницы (например, какого-то элемента, характерного для страницы)
            page.wait_for_selector("body", timeout=30000)

            # Получаем куки
            cookies = context.cookies()
            print("\nПолученные куки:")
            for cookie in cookies:
                print(f"Name: {cookie['name']}, Value: {cookie['value']}, Domain: {cookie['domain']}")

            return cookies

        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None
        finally:
            # Закрываем браузер
            context.close()
            browser.close()