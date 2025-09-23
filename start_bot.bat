@echo off
REM ===== Активируем виртуальное окружение =====
call .venv\Scripts\activate

REM ===== Запускаем бота =====
python main.py

REM ===== Ожидаем закрытия =====
pause
