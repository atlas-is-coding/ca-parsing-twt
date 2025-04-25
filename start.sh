#!/bin/bash

# Проверка и установка Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew не найден, устанавливаем..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Добавление Homebrew в PATH (для macOS)
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
    python3 -m venv $VENV_DIR
    source $VENV_DIR/bin/activate
    # Установка зависимостей для нового venv
    if [ -f "requirements.txt" ]; then
        echo "Устанавливаем зависимости из requirements.txt..."
        pip install -r requirements.txt
    else
        echo "Файл requirements.txt не найден"
    fi
else
    echo "Активируем существующее виртуальное окружение..."
    source $VENV_DIR/bin/activate
fi

# Запуск main.py с sudo
if [ -f "main.py" ]; then
    echo "Запускаем main.py..."
    sudo python3 main.py
else
    echo "Ошибка: main.py не найден"
    exit 1
fi