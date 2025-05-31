# mcmd.py

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

def set_gui_hook(name, func):
    gui_hooks[name] = func

def add_command(name, arg_count, func, start='', end=''):
    commands[name] = Command(name, arg_count, func, start, end)

def compile(command_str):
    command_str = command_str.strip()
    if not command_str:
        return "Пустая команда"

    for name, cmd in commands.items():
        start = cmd.start
        end = cmd.end
        if start and end:
            if command_str.startswith(start + name) and command_str.endswith(end):
                inner = command_str[len(start + name):]
                if inner.startswith('(') and inner.endswith(')'+end):
                    params = inner[1:-1-len(end)].strip()
                else:
                    params = inner[1:-1].strip()
                args = [p.strip() for p in params.split(',')] if params else []
                if cmd.arg_count != len(args):
                    return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                try:
                    return cmd.func(*args)
                except Exception as e:
                    return f"Ошибка в функции команды '{name}': {e}"
            elif command_str.startswith(start + name) and command_str.endswith(')'+end):
                params = command_str[len(start + name)+1:-1-len(end)].strip()
                args = [p.strip() for p in params.split(',')] if params else []
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
                    args = [p.strip() for p in params.split(',')] if params else []
                    if cmd.arg_count != len(args):
                        return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                    try:
                        return cmd.func(*args)
                    except Exception as e:
                        return f"Ошибка в функции команды '{name}': {e}"
        elif end:
            if command_str.startswith(name) and command_str.endswith(end):
                inner = command_str[len(name):]
                if inner.startswith('(') and inner.endswith(')'+end):
                    params = inner[1:-1-len(end)].strip()
                else:
                    params = inner[1:-1].strip()
                args = [p.strip() for p in params.split(',')] if params else []
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
                    args = [p.strip() for p in params.split(',')] if params else []
                    if cmd.arg_count != len(args):
                        return f"Команда '{name}' требует {cmd.arg_count} параметров, получено {len(args)}"
                    try:
                        return cmd.func(*args)
                    except Exception as e:
                        return f"Ошибка в функции команды '{name}': {e}"

    try:
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
        except Exception as e2:
            return f"Неизвестная команда или ошибка Python: {e2}"

def help() :
   return "help"

def sd ():
    with open("scripts/test_sys.bat", "r") as file:
        content = file.read()
        print(content)
        
        
def install ():
    with open("scripts/inst.bat", "r") as file:
        content = file.read()
        print(content)


def exitf():
    exit()

add_command ("help", 0, help)
add_command ("sys_dia", 0, sd)
add_command ("install", 0, install)
add_command ("exit", 0, exitf)