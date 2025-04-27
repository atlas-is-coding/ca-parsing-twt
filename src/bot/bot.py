import os
import asyncio
import logging
import tempfile
import uuid
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.utils import convert_to_network_type, convert_to_balance_network_type, convert_to_nft_network_type
from src.parsers.ca import CAParser
from src.parsers.nftca import NftCAParser
from src.parsers.balance import BalanceParser
from src.twitter import TwitterService
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем состояния
class SettingsStates(StatesGroup):
    min_balance = State()
    max_balance = State()
    min_token_balance = State()
    min_followers = State()

# Создаем роутер для обработки callback-запросов
settings_router = Router()
general_router = Router()


def update_env_file(file_path: str, key: str, new_value: str) -> bool:
    try:
        # Читаем существующий .env файл
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # Флаг, найден ли ключ
        key_found = False
        # Новое содержимое файла
        new_lines = []
        
        # Проходим по всем строкам
        for line in lines:
            # Пропускаем пустые строки и комментарии
            if line.strip() and not line.strip().startswith('#'):
                # Проверяем, содержит ли строка нужный ключ
                if line.strip().startswith(f"{key}="):
                    # Обновляем строку с новым значением
                    new_lines.append(f"{key}={new_value}\n")
                    key_found = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Если ключ не найден, добавляем его в конец
        if not key_found:
            new_lines.append(f"{key}={new_value}\n")
        
        # Записываем обновленное содержимое обратно в файл
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(new_lines)
            
        return True
    
    except Exception as e:
        print(f"❌ Ошибка при обновлении .env файла: {str(e)}")
        return False


def read_env_file(file_path='.env'):
    config = {
        'MIN_BALANCE_USD': 0.0,
        'MAX_BALANCE_USD': 0.0,
        'MIN_TOKEN_BALANCE_USD': 0.0,
        'MIN_FOLLOWERS': 0
    }
    
    try:
        with open(file_path, 'r') as file:
            for line in file:
                # Пропускаем пустые строки и комментарии
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Разделяем строку на ключ и значение
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Присваиваем значения нужным ключам
                    if key == 'MIN_BALANCE_USD':
                        config['MIN_BALANCE_USD'] = float(value)
                    elif key == 'MAX_BALANCE_USD':
                        config['MAX_BALANCE_USD'] = float(value)
                    elif key == 'MIN_TOKEN_BALANCE_USD':
                        config['MIN_TOKEN_BALANCE_USD'] = float(value)
                    elif key == 'MIN_FOLLOWERS':
                        config['MIN_FOLLOWERS'] = int(value)
    
    except FileNotFoundError:
        print(f"Файл {file_path} не найден")
    except ValueError as e:
        print(f"❌ Ошибка преобразования значения: {e}")
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
    
    return config

# Bot token from environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище активных задач (chat_id -> список задач)
active_tasks = {}
active_tasks_lock = asyncio.Lock()
cancel_flags = {}  # Флаг отмены для каждого chat_id
cancel_flags_lock = asyncio.Lock()

dp.include_router(settings_router)
dp.include_router(general_router)
# Temporary storage for contract addresses (to work around Telegram's callback data size limit)
contract_storage = {}

# List of supported networks
NETWORKS = ["Solana", "Ethereum", "Binance Chain", "Base", "Arbitrum", "Optimism", "Polygon"]
# List of supported EVM networks for NFT
EVM_NFT_NETWORKS = ["Ethereum", "Binance Chain", "Base", "Arbitrum", "Optimism", "Polygon"]

# Access control filter
class IsAllowedUser(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return str(message.from_user.id) in ALLOWED_USERS

# Command handler for /start
@general_router.message(Command("start"), IsAllowedUser())
async def cmd_start(message: Message):
    await message.answer(
        "*Добро пожаловть в бота!*\n\n Отправь *контракт адрес* (`токена, нфт`) или *файл* (в формате `адрес:баланс`)",
        parse_mode="Markdown"
    )

@general_router.message(Command("stop"), IsAllowedUser())
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    async with active_tasks_lock:
        if chat_id not in active_tasks or not active_tasks[chat_id]:
            await message.answer("🚫 Нет активных задач для остановки.", parse_mode="Markdown")
            return

        logger.info(f"Отмена задач для чата {chat_id}, количество задач: {len(active_tasks[chat_id])}")
        tasks = active_tasks[chat_id]
        for task in tasks:
            logger.info(f"Отмена задачи {task.get_name()}")
            task.cancel()

        # Устанавливаем флаг отмены
        async with cancel_flags_lock:
            cancel_flags[chat_id] = True

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info(f"Все задачи для чата {chat_id} отменены")
        except Exception as e:
            logger.error(f"Ошибка при отмене задач: {str(e)}")

        if chat_id in active_tasks:
            del active_tasks[chat_id]
        else:
            logger.warning(f"chat_id {chat_id} уже отсутствует в active_tasks")

    await message.answer(
        "🛑 Парсинг остановлен. Промежуточные результаты отправлены (если есть).",
        parse_mode="Markdown"
    )

@general_router.message(Command("settings"), IsAllowedUser())
async def cmd_settings(message: Message):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="💰 Мин. баланс ($)",
        callback_data=f"settings:MIN_BALANCE_USD"
    )

    builder.button(
        text="💰 Макс. баланс ($)",
        callback_data=f"settings:MAX_BALANCE_USD"
    )

    builder.button(
        text="💰 Мин. баланс токена ($)",
        callback_data=f"settings:MIN_TOKEN_BALANCE_USD"
    )

    builder.button(
        text="🧟‍♂️ Мин. кол-во подписчиков",
        callback_data=f"settings:MIN_FOLLOWERS"
    )

    builder.adjust(1, 1, 1, 1)
    
    config = read_env_file()

    await message.answer(
        f"⚙️ *Настройки*\n\n*Текущие значения:*\n• Мин. баланс: `{config['MIN_BALANCE_USD']}`\n• Макс. баланс: `{config['MAX_BALANCE_USD']}`\n• Мин. баланс токена: `{config['MIN_TOKEN_BALANCE_USD']}`\n• Минимальный кол-во подписчиков: `{config['MIN_FOLLOWERS']}`\n\n",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"

    )

# Обработчик callback-запросов для кнопок настроек
@settings_router.callback_query(F.data.startswith("settings:"))
async def handle_settings_callback(callback: CallbackQuery, state: FSMContext):
    # Извлекаем тип настройки из callback_data
    setting = callback.data.split(":")[1]

    # Словарь для маппинга настройки на состояние и текст запроса
    settings_map = {
        "MIN_BALANCE_USD": {
            "state": SettingsStates.min_balance,
            "prompt": "⌨️ *Введите мин. баланс ($): *"
        },
        "MAX_BALANCE_USD": {
            "state": SettingsStates.max_balance,
            "prompt": "⌨️ *Введите макс. баланс ($): *"
        },
        "MIN_TOKEN_BALANCE_USD": {
            "state": SettingsStates.min_token_balance,
            "prompt": "⌨️ *Введите мин. баланс токена ($): *"
        },
        "MIN_FOLLOWERS": {
            "state": SettingsStates.min_followers,
            "prompt": "⌨️ *Введите мин. кол-во подписчиков: *"
        }
    }

    if setting in settings_map:
        # Устанавливаем соответствующее состояние
        await state.set_state(settings_map[setting]["state"])
        # Запрашиваем у пользователя значение
        await callback.message.answer(settings_map[setting]["prompt"], parse_mode="Markdown")
    else:
        await callback.message.answer("*Неизвестная настройка*", parse_mode="Markdown")

    # Подтверждаем обработку callback
    await callback.answer()

# Пример обработки введенного значения для состояния min_balance
@settings_router.message(SettingsStates.min_balance)
async def process_min_balance(message: Message, state: FSMContext):
    try:
        await state.update_data(min_balance=message.text)
        update_env_file(".env", "MIN_BALANCE_USD", message.text)
        await message.answer(f"✅ Мин. баланс установлен: `{message.text} USD`", parse_mode="Markdown")
    except ValueError:
        await message.answer("🔁 *Введите число для установки мин. баланса.*", parse_mode="Markdown")
    finally:
        # Сбрасываем состояние
        await state.clear()

# Аналогичные обработчики для других состояний
@settings_router.message(SettingsStates.max_balance)
async def process_max_balance(message: Message, state: FSMContext):
    try:
        await state.update_data(max_balance=message.text)
        update_env_file(".env", "MAX_BALANCE_USD", message.text)
        load_dotenv()
        await message.answer(f"✅ Макс. баланс установлен: `{message.text} USD`", parse_mode="Markdown")
    except ValueError:
        await message.answer("🔁 *Введите число для установки макс. баланса.*", parse_mode="Markdown")
    finally:
        await state.clear()

@settings_router.message(SettingsStates.min_token_balance)
async def process_min_token_balance(message: Message, state: FSMContext):
    try:
        await state.update_data(min_token_balance=message.text)
        update_env_file(".env", "MIN_TOKEN_BALANCE_USD", message.text)
        load_dotenv()
        await message.answer(f"✅ Мин. баланс токена установлен: `{message.text} USD`", parse_mode="Markdown")
    except ValueError:
        await message.answer("🔁 *Введите число для установки мин. баланса токена.*", parse_mode="Markdown")
    finally:
        await state.clear()

@settings_router.message(SettingsStates.min_followers)
async def process_min_followers(message: Message, state: FSMContext):
    try:
        await state.update_data(min_followers=message.text)
        # MIN_FOLLOWERS
        update_env_file(".env", "MIN_FOLLOWERS", message.text)
        load_dotenv()
        await message.answer(f"✅ Мин. кол-во подписчиков установлено: `{message.text} USD`", parse_mode="Markdown")
    except ValueError:
        await message.answer("🔁 *Введите число для установки мин. кол-во подписчиков.*", parse_mode="Markdown")
    finally:
        await state.clear()


# Handler for unauthorized users
@general_router.message(~IsAllowedUser())
async def unauthorized(message: Message):
    await message.answer("🚫 Вы не авторизованы в боте.", parse_mode="Markdown")

# Handler for contract addresses
@general_router.message(F.text, IsAllowedUser())
async def process_contract_address(message: Message):
    contract_address = message.text.strip()
    
    # Generate a unique ID for this contract address
    contract_id = str(uuid.uuid4())[:8]
    
    # Store the contract address with its ID
    contract_storage[contract_id] = contract_address
    
    # Create inline keyboard with network options
    builder = InlineKeyboardBuilder()
    
    # Add network buttons
    for network in NETWORKS:
        builder.button(
            text=network, 
            callback_data=f"network:{network}:{contract_id}"
        )
    
    # Add NFT buttons
    builder.button(
        text="Solana NFT",
        callback_data=f"nft:sol:{contract_id}"
    )
    
    builder.button(
        text="EVM NFT",
        callback_data=f"nft:evm:{contract_id}"
    )
    
    # Add cancel button
    builder.button(
        text="Отменить", 
        callback_data="cancel"
    )
    
    # Adjust layout: networks in pairs (2 per row), NFT buttons in one row, cancel button on its own row
    builder.adjust(2, 2, 2, 1, 2, 1)
    
    await message.answer(
        f"*🛜 Выберите сеть:*\n`{contract_address}`",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# Модифицированный обработчик для NFT (Solana)
@general_router.callback_query(F.data.startswith("nft:"))
async def process_nft_selection(callback: CallbackQuery):
    _, nft_type, contract_id = callback.data.split(":", 2)
    contract_address = contract_storage.get(contract_id)
    if not contract_address:
        await callback.message.answer(
            "❌ *Ошибка:* Информация о контракте не найдена. Попробуйте снова.\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        return

    chat_id = callback.message.chat.id

    if nft_type == "sol":
        status_message = await callback.message.answer(
            f"🔍 Анализирую NFT контракт на *Solana*\nАдрес: `{contract_address}`\nПожалуйста подождите...",
            parse_mode="Markdown"
        )
        await callback.answer()

        try:
            nft_parser = NftCAParser()
            balance_parser = BalanceParser()

            await status_message.answer(
                f"ℹ️ Получаю NFT холдеров...",
                parse_mode="Markdown"
            )

            holders = await nft_parser.get_holders(contract_address, "sol")
            if not holders:
                await status_message.answer(
                    f"❌ NFT холдеры не найдены для этого контракта\nПроверьте контракт адрес и попробуйте снова.\n\n*Больше информации в консоли*",
                    parse_mode="Markdown"
                )
                return

            holders_count = len(holders)
            await status_message.answer(
                f"✅ Нашлось *{holders_count}* NFT холдеров\n"
                f"⏳ Получаю балансы холдеров... (0%)",
                parse_mode="Markdown"
            )

            balances = []
            total_holders = len(holders)
            batch_size = min(500, max(50, total_holders // 10))
            num_batches = (total_holders + batch_size - 1) // batch_size

            async def parse_nft_balances():
                nonlocal balances
                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, total_holders)
                    current_batch = holders[start_idx:end_idx]

                    batch_balances = await balance_parser.get_balances(current_batch, "sol")
                    if batch_balances:
                        balances.extend(batch_balances)

                    progress_percent = min(99, int((end_idx) / total_holders * 100))
                    await status_message.answer(
                        f"⏳ Получаю балансы холдеров... ({progress_percent}%)",
                        parse_mode="Markdown"
                    )
                return balances

            task = asyncio.create_task(parse_nft_balances())
            if chat_id not in active_tasks:
                active_tasks[chat_id] = []
            active_tasks[chat_id].append(task)

            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Парсинг NFT балансов для Solana прерван пользователем")
                if balances:
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                        temp_file_path = temp_file.name
                        for balance in balances:
                            temp_file.write(f"{balance[0]}:{balance[1]}\n")

                    file_to_send = FSInputFile(temp_file_path,
                                               filename=f"partial_nft_holders_solana_{contract_address[:10]}.txt")
                    await callback.message.answer_document(
                        file_to_send,
                        caption=f"📊 Промежуточные результаты для `{contract_address}`"
                    )
                    await status_message.answer(
                        f"🛑 Парсинг прерван. Промежуточные результаты: *{len(balances)} холдеров*.",
                        parse_mode="Markdown"
                    )
                    os.unlink(temp_file_path)
                else:
                    await status_message.answer(
                        "🛑 Парсинг прерван. Промежуточные результаты отсутствуют.",
                        parse_mode="Markdown"
                    )
                return

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
                for balance in balances:
                    temp_file.write(f"{balance[0]}:{balance[1]}\n")

            await status_message.answer(
                f"✅ Анализ закончен! Готовлю файл...",
                parse_mode="Markdown"
            )

            file_to_send = FSInputFile(temp_file_path, filename=f"nft_holders_solana_{contract_address[:10]}.txt")
            await callback.message.answer_document(
                file_to_send,
                caption=f"📊 Результат для `{contract_address}`"
            )

            result_message = (
                f"✅ *Анализ закончен*\n\n"
                f"📊 *Детали:*\n"
                f"• Сеть: *Solana*\n"
                f"• Адрес: `{contract_address}`\n\n"
                f"👥 *Нашлось {len(balances)} подходящих NFT холдеров*\n"
                f"📎 Файл с результатами был отправлен."
            )
            await status_message.answer(
                result_message,
                parse_mode="Markdown"
            )

            os.unlink(temp_file_path)
            if contract_id in contract_storage:
                del contract_storage[contract_id]

        except Exception as e:
            logger.error(f"❌ Ошибка анализа контракт адреса: {e}")
            await callback.message.answer(
                f"❌ Ошибка при анализе NFT контракта: `{str(e)}`\n\n*Больше информации в консоли*",
                parse_mode="Markdown"
            )
            if contract_id in contract_storage:
                del contract_storage[contract_id]
        finally:
            if chat_id in active_tasks and task in active_tasks[chat_id]:
                active_tasks[chat_id].remove(task)
                if not active_tasks[chat_id]:
                    del active_tasks[chat_id]

    elif nft_type == "evm":
        # Show EVM networks for NFT
        builder = InlineKeyboardBuilder()
        
        # Add EVM NFT network buttons
        for network in EVM_NFT_NETWORKS:
            builder.button(
                text=network, 
                callback_data=f"nft_network:{network}:{contract_id}"
            )
        
        # Add back button
        builder.button(
            text="🔙 Назад", 
            callback_data=f"back:{contract_id}"
        )
        
        # Add cancel button
        builder.button(
            text="🚫 Отменить", 
            callback_data="cancel"
        )
        
        builder.adjust(2, 1, 1)
        
        await callback.message.answer(
            f"🛜 Выберите сеть для NFT контракта:\n`{contract_address}`",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

# Callback query handler for NFT network selection
@general_router.callback_query(F.data.startswith("nft_network:"))
async def process_nft_network_selection(callback: CallbackQuery):
    # Extract data from callback
    _, network, contract_id = callback.data.split(":", 2)
    
    network_type = convert_to_nft_network_type(network)
    
    # Retrieve the full contract address from storage
    contract_address = contract_storage.get(contract_id)
    if not contract_address:
        await callback.message.answer(
            "❌ *Ошибка:* Информация о контракте не найдена. Попробуйте снова.\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        return
    
    # Show processing message
    status_message = await callback.message.answer(
        f"🔍 Анализирую NFT контракт на *{network}*\nАдрес: `{contract_address}`\n\nПожалуйста подождите...",
        parse_mode="Markdown"
    )
    
    await callback.answer()
    
    try:
        # Create parser instances
        nft_parser = NftCAParser()
        balance_parser = BalanceParser()
        
        # Update status message
        await status_message.answer(
            f"ℹ️ Получаю NFT холдеров...",
            parse_mode="Markdown"
        )
        
        # Get holders for the NFT contract address
        holders = await nft_parser.get_holders(contract_address, network_type)
        
        if not holders:
            await status_message.answer(
                f"❌ NFT холдеры не найдены для контракта *{network}*.\nПроверьте контракт адрес и попробуйте снова.\n\n*Больше информации в консоли*",
                parse_mode="Markdown"
            )
            return
            
        # Show progress after getting holders
        holders_count = len(holders)
        await status_message.answer(
            f"✅ Нашлось *{holders_count}* NFT холдеров\n"
            f"⏳ Получаю балансы... (0%)",
            parse_mode="Markdown"
        )
        
        # Process balances with progress updates
        balances = []
        total_holders = len(holders)
        
        # Define batch size for processing
        batch_size = min(500, max(50, total_holders // 10))  # At least 10, at most 100, or ~10% of total
        
        # Calculate how many batches we'll process
        num_batches = (total_holders + batch_size - 1) // batch_size  # Ceiling division
        
        # Process holders in batches
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_holders)
            
            # Get the current batch of holders
            current_batch = holders[start_idx:end_idx]
            
            # Get balances for this batch
            balance_network_type = convert_to_balance_network_type(network)
            batch_balances = await balance_parser.get_balances(current_batch, balance_network_type)
            if batch_balances:
                balances.extend(batch_balances)
            
            # Update progress after each batch
            progress_percent = min(99, int((end_idx) / total_holders * 100))
            await status_message.answer(
                f"⏳ Получаю балансы...... ({progress_percent}%)",
                parse_mode="Markdown"
            )
        
        # Create a temporary file to store the results
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
            temp_file_path = temp_file.name
            
            for balance in balances:
                temp_file.write(f"{balance[0]}:{balance[1]}\n")
        
        # Send the file to the user
        await status_message.answer(
            f"✅ Анализ завершен! Готовлю файл...",
            parse_mode="Markdown"
        )
        
        # Create input file from the temp file
        file_to_send = FSInputFile(temp_file_path, filename=f"nft_holders_{network}_{contract_address[:10]}.txt")
        
        # Send document
        await callback.message.answer_document(
            file_to_send,
            caption=f"📊 Результаты анализа `{contract_address}`"
        )
        
        # Final status message
        result_message = (
            f"✅ *Анализ закончен*\n\n"
            f"📊 *Детали:*\n"
            f"• Сеть: *{network}*\n"
            f"• Адрес: `{contract_address}`\n\n"
            f"👥 *Нашлось {len(balances)} подходящих NFT пользователей*\n"
            f"📎 Results file has been sent."
        )
        await status_message.answer(
            result_message,
            parse_mode="Markdown"
        )
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        # Clean up the storage
        if contract_id in contract_storage:
            del contract_storage[contract_id]
        
    except Exception as e:
        logging.error(f"❌ Ошибка при анализе NFT контракта: {e}")
        await callback.message.answer(
            f"❌ Ошибка при анализе NFT контракта: {str(e)}\n\n*Больше информации в консоли*\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        # Clean up storage even on error
        if contract_id in contract_storage:
            del contract_storage[contract_id]

# Callback query handler for back button
@general_router.callback_query(F.data.startswith("back:"))
async def process_back(callback: CallbackQuery):
    # Extract contract_id from callback
    _, contract_id = callback.data.split(":", 1)
    
    # Retrieve the full contract address from storage
    contract_address = contract_storage.get(contract_id)
    if not contract_address:
        await callback.message.answer(
            "❌ *Ошибка:* Информация о контракте не найдена. Попробуйте снова.",
            parse_mode="Markdown"
        )
        return
    
    # Recreate original keyboard with network options
    builder = InlineKeyboardBuilder()
    
    # Add network buttons
    for network in NETWORKS:
        builder.button(
            text=network, 
            callback_data=f"network:{network}:{contract_id}"
        )
    
    # Add NFT buttons
    builder.button(
        text="Solana NFT",
        callback_data=f"nft:solana:{contract_id}"
    )
    
    builder.button(
        text="EVM NFT",
        callback_data=f"nft:evm:{contract_id}"
    )
    
    # Add cancel button
    builder.button(
        text="Отменить", 
        callback_data="cancel"
    )
    
    # Adjust layout: networks in pairs (2 per row), NFT buttons in one row, cancel button on its own row
    builder.adjust(2, 2, 2, 1, 2, 1)
    
    await callback.message.answer(
        f"🛜 Выберите сеть:\n`{contract_address}`",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@general_router.callback_query(F.data.startswith("network:"))
async def process_network_selection(callback: CallbackQuery):
    _, network, contract_id = callback.data.split(":", 2)
    contract_address = contract_storage.get(contract_id)
    if not contract_address:
        await callback.message.answer(
            "❌ *Ошибка:* Информация о контракте не найдена. Попробуйте снова.\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        return

    network_type = convert_to_network_type(network)
    balance_network_type = convert_to_balance_network_type(network)
    chat_id = callback.message.chat.id

    status_message = await callback.message.answer(
        f"🔍 Анализирую контракт на *{network}*\nАдрес: `{contract_address}`\n\nПожалуйста подождите...",
        parse_mode="Markdown"
    )
    await callback.answer()

    try:
        ca_parser = CAParser()
        balance_parser = BalanceParser()

        await status_message.answer(f"ℹ️ Получаю холдеров...", parse_mode="Markdown")
        holders = await ca_parser.get_holders(contract_address, network_type)

        if not holders:
            await status_message.answer(
                f"❌ Холдеры не найдены для контракта *{network}*.\nПроверьте контракт адрес и попробуйте снова.\n\n*Больше информации в консоли*",
                parse_mode="Markdown"
            )
            return

        holders_count = len(holders)
        await status_message.answer(
            f"✅ Нашлось *{holders_count}* холдеров\n⏳ Получаю балансы... (0%)",
            parse_mode="Markdown"
        )

        balances = []
        total_holders = len(holders)
        batch_size = min(100, max(50, total_holders // 10))
        num_batches = (total_holders + batch_size - 1) // batch_size

        batch_tasks = []

        # Инициализируем флаг отмены
        async with cancel_flags_lock:
            cancel_flags[chat_id] = False

        async def parse_balances():
            nonlocal balances
            for batch_idx in range(num_batches):
                # Проверяем флаг отмены перед началом батча
                async with cancel_flags_lock:
                    if cancel_flags.get(chat_id, False):
                        logger.info(f"Команда /stop вызвана для {chat_id}, прерываю цикл батчей")
                        break

                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, total_holders)
                current_batch = holders[start_idx:end_idx]

                if asyncio.current_task().cancelled():
                    logger.info(f"Задача parse_balances для {network} отменена перед батчем {batch_idx + 1}")
                    raise asyncio.CancelledError()

                batch_task = asyncio.create_task(
                    balance_parser.get_balances(current_batch, balance_network_type),
                    name=f"get_balances_batch_{batch_idx}"
                )
                batch_tasks.append(batch_task)

                try:
                    batch_balances = await batch_task
                    if batch_balances:
                        balances.extend(batch_balances)
                except asyncio.CancelledError:
                    logger.info(f"Задача get_balances для батча {batch_idx + 1} отменена")
                    if not batch_task.done():
                        batch_task.cancel()
                    raise

                progress_percent = min(99, int((end_idx) / total_holders * 100))
                await status_message.answer(
                    f"⏳ Получаю балансы... ({progress_percent}%)",
                    parse_mode="Markdown"
                )
            return balances

        task = asyncio.create_task(parse_balances(), name=f"parse_balances_{network}_{contract_id}")
        async with active_tasks_lock:
            if chat_id not in active_tasks:
                active_tasks[chat_id] = []
            active_tasks[chat_id].append(task)

        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Парсинг балансов для {network} прерван пользователем")
            # Отменяем все задачи батчей
            for batch_task in batch_tasks:
                if not batch_task.done():
                    logger.info(f"Отмена задачи {batch_task.get_name()}")
                    batch_task.cancel()
            await asyncio.gather(*[bt for bt in batch_tasks if not bt.done()], return_exceptions=True)

            if balances:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                    temp_file_path = temp_file.name
                    for balance in balances:
                        temp_file.write(f"{balance[0]}:{balance[1]}\n")

                file_to_send = FSInputFile(temp_file_path,
                                           filename=f"partial_holders_{network}_{contract_address[:10]}.txt")
                await callback.message.answer_document(
                    file_to_send,
                    caption=f"📊 Промежуточные результаты для `{contract_address}`"
                )
                await status_message.answer(
                    f"🛑 Парсинг прерван. Промежуточные результаты: *{len(balances)} холдеров*.",
                    parse_mode="Markdown"
                )
                os.unlink(temp_file_path)
            else:
                await status_message.answer(
                    "🛑 Парсинг прерван. Промежуточные результаты отсутствуют.",
                    parse_mode="Markdown"
                )
            return

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
            temp_file_path = temp_file.name
            for balance in balances:
                temp_file.write(f"{balance[0]}:{balance[1]}\n")

        await status_message.answer(f"✅ Анализ завершен! Готовлю ваш файл...", parse_mode="Markdown")
        file_to_send = FSInputFile(temp_file_path, filename=f"holders_{network}_{contract_address[:10]}.txt")
        await callback.message.answer_document(
            file_to_send,
            caption=f"📊 Результаты для `{contract_address}`"
        )

        result_message = (
            f"✅ *Анализ завершен*\n\n"
            f"📊 *Детали:*\n"
            f"• Сеть: *{network}*\n"
            f"• Адрес: `{contract_address}`\n\n"
            f"👥 *Нашлось {len(balances)} подходящих холдеров*\n"
            f"📎 Файл с результатами отправлен."
        )
        await status_message.answer(result_message, parse_mode="Markdown")

        os.unlink(temp_file_path)
        if contract_id in contract_storage:
            del contract_storage[contract_id]

    except Exception as e:
        logger.error(f"❌ Ошибка при анализе контракта: {e}")
        await callback.message.answer(
            f"❌ Ошибка при анализе контракта: `{str(e)}`\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        if contract_id in contract_storage:
            del contract_storage[contract_id]
    finally:
        async with active_tasks_lock:
            if chat_id in active_tasks and task in active_tasks[chat_id]:
                active_tasks[chat_id].remove(task)
        # Очищаем флаг отмены
        async with cancel_flags_lock:
            if chat_id in cancel_flags:
                del cancel_flags[chat_id]

# Callback query handler for cancel button
@general_router.callback_query(F.data == "cancel")
async def process_cancel(callback: CallbackQuery):
    # Delete the message
    await callback.message.delete()
    
    await callback.answer("❌ Отменено")


# Модифицированный обработчик для Twitter анализа
@general_router.message(F.document, IsAllowedUser())
async def process_document(message: Message):
    document = message.document
    if not document.file_name.endswith('.txt'):
        await message.answer(
            "❌ Отправьте `.txt` файл.",
            parse_mode="Markdown"
        )
        return

    file_id = document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as temp_file:
        temp_file_path = temp_file.name

    await bot.download_file(file_path, temp_file_path)

    try:
        with open(temp_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        invalid_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if ':' not in line or len(line.split(':')) != 2:
                invalid_lines.append((i + 1, line))

        if invalid_lines:
            error_message = "❌ Ошибка в формате файла. Каждая строка должна быть в виде `'wallet:balance'`.\n\nПлохие строки:"
            for idx, (line_num, line_content) in enumerate(invalid_lines[:5]):
                error_message += f"\nСтрока {line_num}: {line_content}"
            if len(invalid_lines) > 5:
                error_message += f"\n... и еще {len(invalid_lines) - 5} строк"
            await message.answer(error_message, parse_mode="Markdown")
            os.unlink(temp_file_path)
            return

        status_message = await message.answer(
            "✅ Формат верный. Начинаю анализ Твиттеров...",
            parse_mode="Markdown"
        )

        try:
            twitter_service = TwitterService()
            wallets = [line.strip().split(':')[0] for line in lines if line.strip()]
            chat_id = message.chat.id

            await status_message.answer(
                f"🔍 Начинаю Twitter анализ для {len(wallets)} кошельков...\n",
                parse_mode="Markdown"
            )

            semaphore = asyncio.Semaphore(20)
            results = []

            async def process_wallet(wallet):
                async with semaphore:
                    try:
                        result = await twitter_service.analyze_tweets(wallet)
                        return wallet, result if result else None
                    except Exception as e:
                        logger.error(f"❌ Ошибка при анализе кошелька {wallet}: {str(e)}")
                        return wallet, None

            tasks = [process_wallet(wallet) for wallet in wallets]
            if chat_id not in active_tasks:
                active_tasks[chat_id] = []
            active_tasks[chat_id].extend(tasks)

            completed = 0
            try:
                for future in asyncio.as_completed(tasks):
                    wallet, result = await future
                    if result:
                        results.append((wallet, result))

                    completed += 1
                    if completed % 50 == 0 or completed == len(wallets):
                        progress = min(99, int(completed / len(wallets) * 100))
                        await status_message.answer(
                            f"⏳ Прогресс: {progress}% ({completed}/{len(wallets)})",
                            parse_mode="Markdown"
                        )
            except asyncio.CancelledError:
                logger.info(f"Twitter анализ прерван пользователем")
                if results:
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as output_file:
                        output_file_path = output_file.name
                        for wallet, result in results:
                            status = result.status
                            if status not in ["GREEN", "YELLOW"]:
                                continue
                            username = result.selected_user if result.selected_user else "N/A"
                            output_file.write(f"{status}:{wallet}:https://x.com/{username}\n")

                    file_to_send = FSInputFile(output_file_path, filename="partial_twitter_analysis_results.txt")
                    await message.answer_document(
                        file_to_send,
                        caption="📊 Промежуточные результаты Twitter анализа"
                    )
                    await status_message.answer(
                        f"🛑 Анализ прерван. Промежуточные результаты: *{len(results)} кошельков*.",
                        parse_mode="Markdown"
                    )
                    os.unlink(output_file_path)
                else:
                    await status_message.answer(
                        "🛑 Анализ прерван. Промежуточные результаты отсутствуют.",
                        parse_mode="Markdown"
                    )
                os.unlink(temp_file_path)
                return

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as output_file:
                output_file_path = output_file.name
                for wallet, result in results:
                    status = result.status
                    if status not in ["GREEN", "YELLOW"]:
                        continue
                    username = result.selected_user if result.selected_user else "N/A"
                    output_file.write(f"{status}:{wallet}:https://x.com/{username}\n")

            file_to_send = FSInputFile(output_file_path, filename="twitter_analysis_results.txt")
            await message.answer_document(
                file_to_send,
                caption="📊 Результаты Twitter анализа"
            )

            await status_message.answer(
                f"✅ *Анализ завершен*\n\n"
                f"• Проанализировано {len(wallets)} кошельков\n"
                f"• Нашлись результаты для {len(results)} кошельков\n"
                f"📎 Файл с результатами был отправлен.",
                parse_mode="Markdown"
            )

            os.unlink(temp_file_path)
            os.unlink(output_file_path)

        except Exception as e:
            logger.error(f"❌ Ошибка во время Twitter анализа: {e}")
            await status_message.answer(
                f"❌ Ошибка во время Twitter анализа: {str(e)}\n\n*Больше информации в консоли*",
                parse_mode="Markdown"
            )
            if 'temp_file_path' in locals():
                os.unlink(temp_file_path)
        finally:
            if chat_id in active_tasks:
                for task in tasks:
                    if task in active_tasks[chat_id]:
                        active_tasks[chat_id].remove(task)
                if not active_tasks[chat_id]:
                    del active_tasks[chat_id]

    except Exception as e:
        logger.error(f"❌ Ошибка при обработка файла: {e}")
        await message.answer(
            f"❌ Ошибка при обработка файла: {str(e)}\n\n*Больше информации в консоли*",
            parse_mode="Markdown"
        )
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)