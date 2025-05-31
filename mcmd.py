# mcmd.py

import subprocess
import sys
import os
import ast
import shlex
from tkinter import *


class Command:
    def __init__(self, name, arg_count, func, start='', end=''):
        self.name = name
        self.arg_count = arg_count
        self.func = func
        self.start = start
        self.end = end


commands = {}
variables = {}
gui_hooks = {}
current_process = None  # Глобальная переменная для хранения активного процесса


def set_gui_hook(name, func):
    gui_hooks[name] = func


def add_command(name, arg_count, func, start='', end=''):
    commands[name] = Command(name, arg_count, func, start, end)


def split_args(params):
    """Улучшенный парсер аргументов с поддержкой строк"""
    parts = []
    current = []
    in_string = False
    string_char = None
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0

    for i, char in enumerate(params):
        if char in ('"', "'") and not in_string:
            in_string = True
            string_char = char
        elif char == string_char and in_string:
            # Проверка на экранированные кавычки
            if i > 0 and params[i - 1] == '\\':
                # Убираем экранирование
                current[-1] = char
            else:
                in_string = False
                string_char = None

        if char == '(': paren_depth += 1
        if char == ')': paren_depth -= 1
        if char == '{': brace_depth += 1
        if char == '}': brace_depth -= 1
        if char == '[': bracket_depth += 1
        if char == ']': bracket_depth -= 1

        # Разделитель только если не внутри строки и не внутри скобок
        if char == ',' and not in_string and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        parts.append(''.join(current).strip())
    return parts


def try_eval(arg):
    """Пытается преобразовать аргумент в Python-объект"""
    try:
        # Пробуем распознать как строку в кавычках
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]
        return ast.literal_eval(arg)
    except:
        return arg  # оставить как строку/идентификатор


def cmd_exec(command_str):
    """Выполняет системную команду"""
    global current_process

    # Убираем кавычки если они есть
    if command_str.startswith('"') and command_str.endswith('"'):
        command_str = command_str[1:-1]
    elif command_str.startswith("'") and command_str.endswith("'"):
        command_str = command_str[1:-1]

    try:
        # Добавляем системные пути для корректного выполнения команд
        env = os.environ.copy()
        if sys.platform == "win32":
            env["PATH"] += os.pathsep + r"C:\Windows\System32"
        else:
            env["PATH"] += os.pathsep + "/usr/bin" + os.pathsep + "/bin"

        # Определяем shell в зависимости от ОС
        shell = sys.platform.startswith('win')

        # Выполняем команду
        process = subprocess.Popen(
            command_str,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        current_process = process

        # Собираем вывод в реальном времени
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                # Сохраняем строку как есть (без rstrip) для сохранения форматирования
                output_lines.append(line)

        # Ждем завершения процесса
        process.wait()
        current_process = None

        # Формируем результат
        result = "".join(output_lines)
        return result if result else "Команда выполнена успешно"

    except FileNotFoundError as e:
        return f"Команда не найдена: {command_str}. Убедитесь, что команда установлена и доступна в PATH."
    except Exception as e:
        if current_process:
            current_process.terminate()
            current_process = None
        return f"Ошибка выполнения команды: {str(e)}"


def cmd_init(system_type=None):
    """Инициализация командной строки"""
    if system_type:
        return f"Командная строка инициализирована для {system_type}"
    else:
        # Автоматическое определение системы
        if sys.platform.startswith('win'):
            return "Командная строка инициализирована для Windows"
        elif sys.platform.startswith('linux'):
            return "Командная строка инициализирована для Linux"
        elif sys.platform.startswith('darwin'):
            return "Командная строка инициализирована для macOS"
        else:
            return "Командная строка инициализирована (система не определена)"


def cmd_kill():
    """Прерывание выполнения текущей команды"""
    global current_process
    if current_process:
        try:
            # Пытаемся корректно завершить процесс
            current_process.terminate()
            try:
                # Даем процессу время на завершение
                current_process.wait(timeout=2)
            except:
                # Принудительно завершаем, если не отвечает
                current_process.kill()
            current_process = None
            return "Выполнение команды прервано"
        except Exception as e:
            return f"Не удалось прервать выполнение команды: {str(e)}"
    return "Нет активных команд для прерывания"


def help():
    help_text = """Доступные команды:
- help: Показать эту справку
- sys_dia: Показать системную диагностику
- install: Показать скрипт установки
- exit: Выйти из программы
- cmd("команда"): Выполнить системную команду
- cmd_init: Инициализировать командную строку
- cmd_kill: Прервать выполняющуюся команду

Примеры:
cmd("pip list")     - Показать установленные пакеты
cmd("python --version") - Показать версию Python
cmd("dir")          - Показать содержимое папки (Windows)
cmd("ls")           - Показать содержимое папки (Linux/Mac)"""
    return help_text


def sd():
    try:
        with open("scripts/test_sys.bat", "r", encoding="utf-8") as file:
            content = file.read()
            return content
    except Exception as e:
        return f"Ошибка чтения файла: {str(e)}"


def install():
    result0 = compile("cmd_init()")
    result1 = compile("cmd ollama pull tinyllama")
    result2 = compile("cmd pip install requests pillow numpy transformers flask flask-cors tk pygetwindow pyscreeze streamlit rich")
    result3 = compile("cmd ollama serve")
    result = f"""
    {result0}
    
    
    
    $  cmd ollama pull tinyllama
    {result1}
    
    
    
    $  cmd pip install requests pillow numpy transformers flask flask-cors tk pygetwindow pyscreeze streamlit rich
    {result2}
    
    
    
    $  cmd ollama serve
    {result3}
    
    
    
    ============= done =============
    """
    return result

def exitf():
    exit()

def comandsHelp():
    comandHelp = Tk()
    comandHelp.geometry("700x700")
    super().__init__()
    comandHelp.title("T-Code Professional")
    comandHelp.configure(bg="#121212")


# Регистрируем все команды
add_command("help", 0, help)
add_command("all_comands", 0, comandsHelp)
add_command("sys_dia", 0, sd)
add_command("program_init", 0, install)
add_command("exit", 0, exitf)
add_command("cmd", 1, cmd_exec)  # 1 аргумент - строка команды
add_command("cmd_init", 0, cmd_init)
add_command("cmd_kill", 0, cmd_kill)


def compile(command_str):
    command_str = command_str.strip()
    if not command_str:
        return "Пустая команда"

    # Специальная обработка для команд в формате cmd без кавычек
    if command_str.startswith("cmd ") and "(" not in command_str and ")" not in command_str:
        command_str = f'cmd("{command_str[4:]}")'

    for name, cmd in commands.items():
        start = cmd.start
        end = cmd.end
        if start and end:
            if command_str.startswith(start + name) and command_str.endswith(end):
                inner = command_str[len(start + name):]
                if inner.startswith('(') and inner.endswith(')' + end):
                    params = inner[1:-1 - len(end)].strip()
                else:
                    params = inner[1:-1].strip()

                # Используем улучшенный парсер аргументов
                args = split_args(params) if params else []
                args = [try_eval(arg) for arg in args]

                if cmd.arg_count != len(args):
                    return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                try:
                    return cmd.func(*args)
                except Exception as e:
                    return f"Ошибка в функции команды '{name}': {e}"
            elif command_str.startswith(start + name) and command_str.endswith(')' + end):
                params = command_str[len(start + name) + 1:-1 - len(end)].strip()

                # Используем улучшенный парсер аргументов
                args = split_args(params) if params else []
                args = [try_eval(arg) for arg in args]

                if cmd.arg_count != len(args):
                    return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                try:
                    return cmd.func(*args)
                except Exception as e:
                    return f"Ошибка в функции команды '{name}': {e}"
        elif start:
            if command_str.startswith(start + name):
                inner = command_str[len(start + name):]
                if inner.startswith('(') and inner.endswith(')'):
                    params = inner[1:-1].strip()

                    # Используем улучшенный парсер аргументов
                    args = split_args(params) if params else []
                    args = [try_eval(arg) for arg in args]

                    if cmd.arg_count != len(args):
                        return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                    try:
                        return cmd.func(*args)
                    except Exception as e:
                        return f"Ошибка в функции команды '{name}': {e}"
        elif end:
            if command_str.startswith(name) and command_str.endswith(end):
                inner = command_str[len(name):]
                if inner.startswith('(') and inner.endswith(')' + end):
                    params = inner[1:-1 - len(end)].strip()
                else:
                    params = inner[1:-1].strip()

                # Используем улучшенный парсер аргументов
                args = split_args(params) if params else []
                args = [try_eval(arg) for arg in args]

                if cmd.arg_count != len(args):
                    return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                try:
                    return cmd.func(*args)
                except Exception as e:
                    return f"Ошибка в функции команды '{name}': {e}"
        else:
            if command_str.startswith(name):
                inner = command_str[len(name):]
                if inner.startswith('(') and inner.endswith(')'):
                    params = inner[1:-1].strip()

                    # Используем улучшенный парсер аргументов
                    args = split_args(params) if params else []
                    args = [try_eval(arg) for arg in args]

                    if cmd.arg_count != len(args):
                        return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                    try:
                        return cmd.func(*args)
                    except Exception as e:
                        return f"Ошибка в функции команды '{name}': {e}"

    try:
        # Автоматическое преобразование команд типа "cmd <command>"
        if command_str.startswith("cmd ") and "(" not in command_str:
            return cmd_exec(command_str[4:])

        if command_str.startswith('print(') and command_str.endswith(')'):
            var_name = command_str[6:-1].strip()
            if var_name in variables:
                return variables[var_name]
            else:
                return str(eval(var_name, {}, variables))
        result = eval(command_str, {}, variables)
        return str(result)
    except Exception as e:
        try:
            exec(command_str, {}, variables)
            return "Команда выполнена"
        except Exception as e2:
            return f"Неизвестная команда или ошибка Python: {e2}"
