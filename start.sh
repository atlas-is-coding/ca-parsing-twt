#!/bin/bash

# Путь для сохранения репозитория
DESKTOP_DIR="$HOME/Desktop"
REPO_URL="https://github.com/atlas-is-coding/ca-parsing-twt/archive/refs/heads/main.zip"
ZIP_FILE="$DESKTOP_DIR/ca-parsing-twt.zip"
EXTRACTED_DIR="$DESKTOP_DIR/ca-parsing-twt-main"

# Скачивание репозитория
echo "Скачиваем репозиторий..."
curl -L "$REPO_URL" -o "$ZIP_FILE"

# Проверка успешности загрузки
if [ $? -ne 0 ]; then
    echo "Ошибка при скачивании репозитория"
    exit 1
fi

# Разархивирование на рабочий стол
echo "Разархивируем репозиторий..."
unzip -o "$ZIP_FILE" -d "$DESKTOP_DIR"

# Проверка успешности разархивирования
if [ $? -ne 0 ]; then
    echo "Ошибка при разархивировании"
    rm -f "$ZIP_FILE"
    exit 1
fi

# Удаление zip файла
rm -f "$ZIP_FILE"

# Запрос пути к папке у пользователя
echo "Введите полный путь к папке с файлами для переноса в проект:"
read -r SOURCE_DIR

# Проверка существования указанной папки
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Ошибка: Указанная папка не существует"
    exit 1
fi

# Перенос содержимого указанной папки в разархивированный проект
echo "Переносим файлы из $SOURCE_DIR в $EXTRACTED_DIR..."
cp -r "$SOURCE_DIR"/* "$EXTRACTED_DIR/"

# Проверка успешности копирования
if [ $? -ne 0 ]; then
    echo "Ошибка при переносе файлов"
    exit 1
fi

# Переход в директорию проекта
cd "$EXTRACTED_DIR" || {
    echo "Ошибка: Не удалось перейти в директорию проекта"
    exit 1
}

# Проверка и установка Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew не найден, устанавливаем..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "Homebrew уже установлен"
fi

# Проверка и установка Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 не найден, устанавливаем..."
    brew install python3
else
    echo "Python3 уже установлен"
fi

# Установка корневых сертификатов для Python
echo "Устанавливаем корневые сертификаты для Python..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
CERT_SCRIPT="/Applications/Python ${PYTHON_VERSION}/Install Certificates.command"
if [ -f "$CERT_SCRIPT" ]; then
    echo "Запускаем Install Certificates.command..."
    sh "$CERT_SCRIPT"
else
    echo "Скрипт Install Certificates.command не найден, устанавливаем certifi..."
    python3 -m pip install certifi
fi

# Проверка и установка pip
if ! command -v pip3 &> /dev/null; then
    echo "pip3 не найден, устанавливаем..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py
    rm get-pip.py
else
    echo "pip3 уже установлен"
fi

# Проверка и создание/активация virtualenv
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Создаем виртуальное окружение..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    if [ -f "requirements.txt" ]; then
        echo "Устанавливаем зависимости из requirements.txt..."
        pip install -r requirements.txt
    else
        echo "Файл requirements.txt не найден"
    fi
else
    echo "Активируем существующее виртуальное окружение..."
    source "$VENV_DIR/bin/activate"
fi

# Проверка и установка Playwright
if ! pip show playwright &> /dev/null; then
    echo "Playwright не найден, устанавливаем..."
    pip install playwright
    echo "Устанавливаем браузеры для Playwright..."
    playwright install
else
    echo "Playwright уже установлен"
    if ! playwright install --dry-run &> /dev/null; then
        echo "Устанавливаем браузеры для Playwright..."
        playwright install
    else
        echo "Браузеры Playwright уже установлены"
    fi
fi

# Запуск main.py
if [ -f "main.py" ]; then
    echo "Запускаем main.py..."
    python3 main.py
else
    echo "Ошибка: main.py не найден"
    exit 1
fi