# Используем легкую официальную версию Python
FROM python:3.12-slim

# Указываем рабочую папку внутри сервера
WORKDIR /app

# Отключаем буферизацию логов, чтобы сразу видеть ошибки в консоли Fly.io
ENV PYTHONUNBUFFERED=1

# Копируем файл со списком библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы бота на сервер
COPY . .

# Команда для запуска бота
CMD ["python", "main.py"]
