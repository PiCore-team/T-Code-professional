import io
import sys
import re
import ast

commands = {}
variables = {}

class Command:
    def __init__(self, name, arg_count, func, start='', end=''):
        self.name = name
        self.arg_count = arg_count
        self.func = func
        self.start = start
        self.end = end

def add_command(name, arg_count, func, start='', end=''):
    commands[name] = Command(name, arg_count, func, start, end)

def split_args(params):
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
            if i > 0 and params[i-1] == '\\':
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

        if char == ',' and not in_string and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        parts.append(''.join(current).strip())
    return parts

def execute_python_code(code):
    code = code.replace('\t', '   ')
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()

    try:
        # Пытаемся разобрать как выражение (eval)
        try:
            expr = ast.parse(code, mode='eval')
            compiled = compile(expr, '<string>', 'eval')
            result = eval(compiled, {}, variables)
            output = f"{result}\n" if result is not None else ""
        except SyntaxError:
            # Если не получилось — исполняем как обычный код (exec)
            exec(code, {}, variables)
            output = ""
        
        sys.stdout = old_stdout
        output += mystdout.getvalue()
        return output.strip() if output else "ОК"

    except Exception as e:
        sys.stdout = old_stdout
        return f"ошибка python: {e}"


def try_eval(arg):
    try:
        return ast.literal_eval(arg)
    except:
        return arg  # оставить как строку/идентификатор

def parse_command_single(command_str):
    for name, cmd in commands.items():
        start = cmd.start
        end = cmd.end

        pattern_parts = []
        if start:
            pattern_parts.append(f"{re.escape(start)}\\s*")
        pattern_parts.append(f"{re.escape(name)}\\s*\\((.*?)\\)")
        if end:
            pattern_parts.append(f"\\s*{re.escape(end)}")

        pattern = "^" + "".join(pattern_parts) + "$"
        match = re.match(pattern, command_str, re.DOTALL)

        if match:
            params = match.group(1).strip()
            try:
                args = [try_eval(arg.strip()) for arg in split_args(params)]
            except Exception as e:
                return f"Ошибка в параметрах: {e}"

            if cmd.arg_count != len(args):
                return f"Нужно {cmd.arg_count} аргументов, получено {len(args)}"

            try:
                return cmd.func(*args)
            except Exception as e:
                return f"Ошибка выполнения: {e}"

    return execute_python_code(command_str)

def parse_command(command_str):
    command_str = command_str.strip()
    if not command_str:
        return "Пустая команда"

    blocks = command_str.splitlines()
    buffer = []
    output = []

    def flush_python_block():
        if buffer:
            py_code = "\n".join(buffer).strip()
            if py_code:
                result = execute_python_code(py_code)
                output.append(result)
            buffer.clear()

    for line in blocks:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("!"):
            flush_python_block()
            result = parse_command_single(stripped)
            output.append(result)
        else:
            buffer.append(line)

    flush_python_block()
    return "\n".join(str(o) for o in output if o)
# ==== Примеры команд ====

def movefunc(x, y):
    return f"Движение: X={x}, Y={y}"

def create_var(name, value):
    variables[name] = value
    return f"Создана {name} = {value}"

add_command("move", 2, movefunc)
add_command("var.create", 2, create_var, start='!', end=';')

def call_command(name, *args):
    if name not in commands:
        raise ValueError(f"Команда '{name}' не найдена")
    cmd = commands[name]
    if len(args) != cmd.arg_count:
        raise ValueError(f"Нужно {cmd.arg_count} аргументов, получено {len(args)}")
    return cmd.func(*args)

def t_compile(command_str):
    return parse_command(command_str)
