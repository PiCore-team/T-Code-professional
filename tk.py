
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog, font
import webbrowser
import os
import re
import compile as c
import mcmd as cmd
import requests
import json
import threading
from datetime import datetime
import time
import subprocess
import ast
import keyword

i = 0

# === Константы для ИИ-агента ===
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "tinyllama"
REQUEST_TIMEOUT = 90

# Упрощенный системный промпт
SYSTEM_PROMPT = """Ты - помощник программиста. Отвечай четко и по делу."""


def process_content(content):
    """Очистка ответа от служебных маркеров"""
    return content.replace('**', '').replace('*', '').strip()


class LineNumbers(tk.Canvas):
    """Класс для отображения номеров строк"""

    def __init__(self, parent, text_widget, **kwargs):
        super().__init__(parent, **kwargs)
        self.text_widget = text_widget
        self.configure(
            width=50,
            bg="#2d2d2d",
            highlightthickness=0,
            borderwidth=0
        )

        # Привязка событий для синхронизации
        self.text_widget.bind('', self.redraw)
        self.text_widget.bind('', self.redraw)
        self.text_widget.bind('', self.redraw)
        self.text_widget.bind('', self.redraw)
        self.text_widget.bind('', self.redraw)

    def redraw(self, event=None):
        """Перерисовка номеров строк"""
        self.delete("all")

        try:
            first_line = self.text_widget.index("@0,0")
            line_num = int(first_line.split('.')[0])

            y_pos = 0
            while True:
                try:
                    dline_info = self.text_widget.dlineinfo(f"{line_num}.0")
                    if dline_info is None:
                        break

                    line_y = dline_info[1]

                    self.create_text(
                        45, line_y + 10,
                        anchor="e",
                        text=str(line_num),
                        fill="#858585",
                        font=("Consolas", 10)
                    )

                    line_num += 1

                    if line_y > self.text_widget.winfo_height():
                        break

                except tk.TclError:
                    break
        except:
            pass

        self.after_idle(self.sync_scroll)

    def sync_scroll(self):
        """Синхронизация прокрутки с текстовым виджетом"""
        try:
            top, bottom = self.text_widget.yview()
            self.configure(scrollregion=self.bbox("all"))
        except:
            pass


class AutoCompleteEntry(tk.Text):
    """Виджет с автодополнением для Python"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Список ключевых слов Python
        self.keywords = keyword.kwlist + [
            'print', 'input', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'tuple',
            'set', 'bool', 'type', 'isinstance', 'hasattr', 'getattr', 'setattr', 'delattr',
            'open', 'close', 'read', 'write', 'readline', 'readlines', 'split', 'join',
            'append', 'extend', 'insert', 'remove', 'pop', 'index', 'count', 'sort', 'reverse',
            'keys', 'values', 'items', 'get', 'update', 'clear', 'copy'
        ]

        self.popup = None
        self.bind('', self.on_key_release)
        self.bind('', self.hide_popup)

    def on_key_release(self, event):
        """Обработка нажатий клавиш для автодополнения"""
        if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Return', 'Tab']:
            self.hide_popup()
            return

        # Получаем текущее слово
        current_pos = self.index(tk.INSERT)
        line_start = current_pos.split('.')[0] + '.0'
        line_text = self.get(line_start, current_pos)

        # Ищем последнее слово
        words = re.findall(r'\w+', line_text)
        if words:
            current_word = words[-1]
            if len(current_word) >= 2:  # Показываем автодополнение после 2 символов
                matches = [kw for kw in self.keywords if kw.startswith(current_word) and kw != current_word]
                if matches:
                    self.show_popup(matches[:10])  # Показываем максимум 10 вариантов
                else:
                    self.hide_popup()
            else:
                self.hide_popup()
        else:
            self.hide_popup()

    def show_popup(self, matches):
        """Показать всплывающее окно с вариантами"""
        if self.popup:
            self.popup.destroy()

        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.configure(bg="#2d2d2d")

        # Позиционирование
        x = self.winfo_rootx() + 50
        y = self.winfo_rooty() + 50
        self.popup.geometry(f"+{x}+{y}")

        # Создаем список вариантов
        listbox = tk.Listbox(self.popup, bg="#2d2d2d", fg="#d4d4d4",
                             selectbackground="#007acc", height=min(len(matches), 10))
        listbox.pack()

        for match in matches:
            listbox.insert(tk.END, match)

        listbox.bind('', lambda e: self.insert_completion(listbox.get(listbox.curselection())))
        listbox.bind('', lambda e: self.insert_completion(listbox.get(listbox.curselection())))

    def insert_completion(self, completion):
        """Вставить выбранное дополнение"""
        current_pos = self.index(tk.INSERT)
        line_start = current_pos.split('.')[0] + '.0'
        line_text = self.get(line_start, current_pos)

        words = re.findall(r'\w+', line_text)
        if words:
            current_word = words[-1]
            # Удаляем текущее неполное слово
            word_start = current_pos.split('.')[0] + '.' + str(int(current_pos.split('.')[1]) - len(current_word))
            self.delete(word_start, current_pos)
            # Вставляем полное слово
            self.insert(word_start, completion)

        self.hide_popup()

    def hide_popup(self, event=None):
        """Скрыть всплывающее окно"""
        if self.popup:
            self.popup.destroy()
            self.popup = None


class CodeAnalyzer:
    """Анализатор кода для поиска ошибок и предупреждений"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def analyze(self, code):
        """Анализ кода Python"""
        self.errors = []
        self.warnings = []

        try:
            # Проверка синтаксиса
            ast.parse(code)
        except SyntaxError as e:
            self.errors.append({
                'line': e.lineno,
                'message': f"Синтаксическая ошибка: {e.msg}",
                'type': 'error'
            })

        # Простые проверки качества кода
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            # Проверка длины строки
            if len(line) > 120:
                self.warnings.append({
                    'line': i,
                    'message': "Строка слишком длинная (>120 символов)",
                    'type': 'warning'
                })

            # Проверка неиспользуемых импортов (упрощенная)
            if line.strip().startswith('import ') and 'import' in line:
                module_name = line.strip().split()[1].split('.')[0]
                if module_name not in code.replace(line, ''):
                    self.warnings.append({
                        'line': i,
                        'message': f"Неиспользуемый импорт: {module_name}",
                        'type': 'warning'
                    })

        return self.errors + self.warnings


class ProjectExplorer:
    """Проводник проекта"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.current_path = os.getcwd()

        self.frame = tk.Frame(parent, bg="#252526")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        header = tk.Label(self.frame, text="Проводник проекта",
                          bg="#252526", fg="#d4d4d4", font=("Segoe UI", 10, "bold"))
        header.pack(pady=5)

        # Дерево файлов
        self.tree = ttk.Treeview(self.frame)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Привязка событий
        self.tree.bind('', self.on_double_click)
        self.tree.bind('', self.show_context_menu)

        # Загрузка текущей директории
        self.load_directory(self.current_path)

    def load_directory(self, path):
        """Загрузка директории в дерево"""
        self.tree.delete(*self.tree.get_children())

        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    self.tree.insert('', 'end', text=f"📁 {item}", values=[item_path])
                else:
                    icon = "🐍" if item.endswith('.py') else "📄"
                    self.tree.insert('', 'end', text=f"{icon} {item}", values=[item_path])
        except PermissionError:
            pass

    def on_double_click(self, event):
        """Обработка двойного клика"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            file_path = item['values'][0]

            if os.path.isfile(file_path):
                self.app.open_file_from_explorer(file_path)
            else:
                self.load_directory(file_path)
                self.current_path = file_path

    def show_context_menu(self, event):
        """Показать контекстное меню"""
        context_menu = tk.Menu(self.parent, tearoff=0)
        context_menu.add_command(label="Новый файл", command=self.new_file)
        context_menu.add_command(label="Новая папка", command=self.new_folder)
        context_menu.add_separator()
        context_menu.add_command(label="Обновить", command=lambda: self.load_directory(self.current_path))

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def new_file(self):
        """Создать новый файл"""
        name = simpledialog.askstring("Новый файл", "Имя файла:")
        if name:
            file_path = os.path.join(self.current_path, name)
            try:
                with open(file_path, 'w') as f:
                    f.write("")
                self.load_directory(self.current_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать файл: {e}")

    def new_folder(self):
        """Создать новую папку"""
        name = simpledialog.askstring("Новая папка", "Имя папки:")
        if name:
            folder_path = os.path.join(self.current_path, name)
            try:
                os.makedirs(folder_path)
                self.load_directory(self.current_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать папку: {e}")


class FindReplaceDialog:
    """Диалог поиска и замены"""

    def __init__(self, parent, text_widget):
        self.parent = parent
        self.text_widget = text_widget
        self.window = None

    def show(self):
        """Показать диалог"""
        if self.window:
            self.window.focus()
            return

        self.window = tk.Toplevel(self.parent)
        self.window.title("Поиск и замена")
        self.window.geometry("400x200")
        self.window.configure(bg="#2d2d2d")

        # Поле поиска
        tk.Label(self.window, text="Найти:", bg="#2d2d2d", fg="#d4d4d4").grid(row=0, column=0, sticky="w", padx=5,
                                                                              pady=5)
        self.find_entry = tk.Entry(self.window, width=30, bg="#1e1e1e", fg="#d4d4d4")
        self.find_entry.grid(row=0, column=1, padx=5, pady=5)

        # Поле замены
        tk.Label(self.window, text="Заменить:", bg="#2d2d2d", fg="#d4d4d4").grid(row=1, column=0, sticky="w", padx=5,
                                                                                 pady=5)
        self.replace_entry = tk.Entry(self.window, width=30, bg="#1e1e1e", fg="#d4d4d4")
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5)

        # Кнопки
        button_frame = tk.Frame(self.window, bg="#2d2d2d")
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        tk.Button(button_frame, text="Найти", command=self.find_next,
                  bg="#007acc", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Заменить", command=self.replace_current,
                  bg="#007acc", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Заменить все", command=self.replace_all,
                  bg="#007acc", fg="white").pack(side=tk.LEFT, padx=5)

        # Привязка клавиш
        self.find_entry.bind('', lambda e: self.find_next())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.find_entry.focus()

    def find_next(self):
        """Найти следующее вхождение"""
        search_text = self.find_entry.get()
        if not search_text:
            return

        # Очищаем предыдущие выделения
        self.text_widget.tag_remove("search", "1.0", tk.END)

        # Ищем текст
        start_pos = self.text_widget.search(search_text, tk.INSERT, tk.END)
        if start_pos:
            end_pos = f"{start_pos}+{len(search_text)}c"
            self.text_widget.tag_add("search", start_pos, end_pos)
            self.text_widget.tag_config("search", background="#ffff00", foreground="#000000")
            self.text_widget.mark_set(tk.INSERT, end_pos)
            self.text_widget.see(start_pos)
        else:
            messagebox.showinfo("Поиск", "Текст не найден")

    def replace_current(self):
        """Заменить текущее выделение"""
        if self.text_widget.tag_ranges("search"):
            replace_text = self.replace_entry.get()
            self.text_widget.delete("search.first", "search.last")
            self.text_widget.insert("search.first", replace_text)
            self.text_widget.tag_remove("search", "1.0", tk.END)

    def replace_all(self):
        """Заменить все вхождения"""
        search_text = self.find_entry.get()
        replace_text = self.replace_entry.get()

        if not search_text:
            return

        content = self.text_widget.get("1.0", tk.END)
        new_content = content.replace(search_text, replace_text)

        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", new_content)

        count = content.count(search_text)
        messagebox.showinfo("Замена", f"Заменено {count} вхождений")

    def close(self):
        """Закрыть диалог"""
        self.text_widget.tag_remove("search", "1.0", tk.END)
        self.window.destroy()
        self.window = None


class ChatMessage:
    """Класс для представления сообщения в чате"""

    def __init__(self, sender, content, timestamp=None, message_type="text"):
        self.sender = sender  # "user", "ai", "system"
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.message_type = message_type  # "text", "code", "error"


class AIRequestManager:
    """Менеджер для управления запросами к ИИ"""

    def __init__(self, callback_func):
        self.callback = callback_func
        self.is_processing = False
        self.current_thread = None
        self.request_queue = []

    def add_request(self, prompt, context=""):
        """Добавление запроса в очередь"""
        if self.is_processing:
            return False

        self.is_processing = True
        self.current_thread = threading.Thread(
            target=self._process_request,
            args=(prompt, context),
            daemon=True
        )
        self.current_thread.start()
        return True

    def _process_request(self, prompt, context):
        """Обработка запроса в отдельном потоке"""
        try:
            response = self._make_api_call(prompt, context)
            self.callback("success", response)
        except Exception as e:
            self.callback("error", str(e))
        finally:
            self.is_processing = False

    def _make_api_call(self, prompt, context):
        """Выполнение API запроса"""
        final_prompt = self._build_prompt(prompt, context)

        data = {
            "model": MODEL,
            "prompt": final_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": 500,
                "stop": ["Пользователь:", "User:", "Human:"],
                "repeat_penalty": 1.1
            }
        }

        response = requests.post(OLLAMA_URL, json=data, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")

        result = response.json()
        return result.get('response', '').strip()

    def _build_prompt(self, user_prompt, context):
        """Построение упрощенного промпта"""
        parts = [SYSTEM_PROMPT]

        if context:
            parts.append(f"\nВот код пользователя:\n{context}")

        parts.append(f"\nВот его запрос: {user_prompt}")
        parts.append("\nОтвет:")

        return "\n".join(parts)

    def cancel_request(self):
        """Отмена текущего запроса"""
        self.is_processing = False


class FileTab:
    def __init__(self, name="Безымянный.tcd", content="", path=None):
        self.name = name
        self.content = content
        self.path = path
        self.saved = True
        self.bookmarks = []  # Закладки в файле


class CodeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("T-Code Professional - Advanced IDE")
        self.geometry("1600x900")
        self.configure(bg="#121212")

        # Темная цветовая схема
        self.colors = {
            "bg": "#121212",
            "editor_bg": "#1e1e1e",
            "editor_fg": "#d4d4d4",
            "line_numbers": "#2d2d2d",
            "tab_bg": "#252526",
            "tab_active": "#007acc",
            "btn_normal": "#3a3d41",
            "btn_hover": "#505357",
            "btn_danger": "#d73a49",
            "debugger_bg": "#1e1e1e",
            "debugger_fg": "#d4d4d4",
            "cmd_bg": "#1e1e1e",
            "cmd_fg": "#d4d4d4",
            "user_msg": "#9cdcfe",
            "ai_msg": "#ce9178",
            "system_msg": "#dcdcaa",
            "error_msg": "#f44747",
            "code_bg": "#1e1e1e",
            "chat_bg": "#252526",
            "input_bg": "#2d2d2d",
            "border": "#3e3e42"
        }

        # Инициализация компонентов
        self.chat_messages = []
        self.ai_request_manager = AIRequestManager(self._handle_ai_response)
        self.code_analyzer = CodeAnalyzer()
        self.find_replace_dialog = None
        self.current_theme = "dark"
        self.font_size = 11

        self.create_menu()
        self.create_widgets()
        self.init_enhanced_ai_agent()

        # Автосохранение каждые 5 минут
        self.auto_save_timer()

    def auto_save_timer(self):
        """Таймер автосохранения"""
        self.auto_save()
        self.after(300000, self.auto_save_timer)  # 5 минут

    def auto_save(self):
        """Автосохранение всех открытых файлов"""
        for i, tab in enumerate(self.file_tabs):
            if tab.path and not tab.saved:
                try:
                    _, editor, _ = self.get_editor_by_index(i)
                    content = editor.get("1.0", tk.END)
                    backup_path = tab.path + ".autosave"
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                except Exception:
                    pass

    def create_menu(self):
        """Создание расширенного меню"""
        menubar = tk.Menu(self, bg=self.colors["bg"], fg="#d4d4d4",
                          activebackground=self.colors["btn_hover"],
                          activeforeground="#ffffff")
        self.config(menu=menubar)

        # Меню "Файл"
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новый файл", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть", command=self.load_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Открыть папку", command=self.open_folder, accelerator="Ctrl+Shift+O")
        file_menu.add_separator()
        file_menu.add_command(label="Сохранить", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Сохранить как", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_command(label="Сохранить все", command=self.save_all_files, accelerator="Ctrl+Alt+S")
        file_menu.add_separator()
        file_menu.add_command(label="Закрыть файл", command=self.close_current_file, accelerator="Ctrl+W")
        file_menu.add_command(label="Выход", command=self.quit, accelerator="Ctrl+Q")

        # Меню "Правка"
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Отменить", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Повторить", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Вырезать", command=self.cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="Копировать", command=self.copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Вставить", command=self.paste, accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Найти", command=self.show_find_replace, accelerator="Ctrl+F")
        edit_menu.add_command(label="Найти и заменить", command=self.show_find_replace, accelerator="Ctrl+H")
        edit_menu.add_command(label="Перейти к строке", command=self.goto_line, accelerator="Ctrl+G")
        edit_menu.add_separator()
        edit_menu.add_command(label="Выделить все", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_command(label="Дублировать строку", command=self.duplicate_line, accelerator="Ctrl+D")
        edit_menu.add_command(label="Удалить строку", command=self.delete_line, accelerator="Ctrl+Shift+K")

        # Меню "Вид"
        view_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="Увеличить шрифт", command=self.increase_font, accelerator="Ctrl+=")
        view_menu.add_command(label="Уменьшить шрифт", command=self.decrease_font, accelerator="Ctrl+-")
        view_menu.add_command(label="Сбросить размер шрифта", command=self.reset_font, accelerator="Ctrl+0")
        view_menu.add_separator()
        view_menu.add_command(label="Переключить тему", command=self.toggle_theme, accelerator="Ctrl+T")
        view_menu.add_command(label="Полноэкранный режим", command=self.toggle_fullscreen, accelerator="F11")
        view_menu.add_separator()
        view_menu.add_command(label="Показать/скрыть проводник", command=self.toggle_explorer, accelerator="Ctrl+B")

        # Меню "Выполнение"
        run_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                           activebackground=self.colors["btn_hover"],
                           activeforeground="#ffffff")
        menubar.add_cascade(label="Выполнение", menu=run_menu)
        run_menu.add_command(label="Запустить", command=self.run_code, accelerator="F5")
        run_menu.add_command(label="Запустить в терминале", command=self.run_in_terminal, accelerator="Ctrl+F5")
        run_menu.add_command(label="Остановить", command=self.stop_execution, accelerator="Ctrl+F2")
        run_menu.add_separator()
        run_menu.add_command(label="Проверить синтаксис", command=self.check_syntax, accelerator="F7")

        # Меню "Инструменты"
        tools_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                             activebackground=self.colors["btn_hover"],
                             activeforeground="#ffffff")
        menubar.add_cascade(label="Инструменты", menu=tools_menu)
        tools_menu.add_command(label="Форматировать код", command=self.format_code, accelerator="Ctrl+Alt+L")
        tools_menu.add_command(label="Анализ кода", command=self.analyze_code, accelerator="Ctrl+Alt+I")
        tools_menu.add_command(label="Добавить закладку", command=self.add_bookmark, accelerator="Ctrl+F11")
        tools_menu.add_command(label="Показать закладки", command=self.show_bookmarks, accelerator="Shift+F11")

        # Меню "ИИ"
        ai_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                          activebackground=self.colors["btn_hover"],
                          activeforeground="#ffffff")
        menubar.add_cascade(label="ИИ", menu=ai_menu)
        ai_menu.add_command(label="Анализ кода", command=self.quick_ai_analysis)
        ai_menu.add_command(label="Объяснить код", command=self.explain_code)
        ai_menu.add_command(label="Предложить улучшения", command=self.suggest_improvements)
        ai_menu.add_command(label="Генерировать документацию", command=self.generate_docs)
        ai_menu.add_command(label="Очистить чат", command=self.clear_chat)

        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Горячие клавиши", command=self.show_shortcuts, accelerator="F1")
        help_menu.add_command(label="О программе", command=self.show_about)

    def is_code_related(self, question):
        """Проверка связи с кодом"""
        code_keywords = [
            'ошибка', 'код', 'исправь', 'почему не работает', 'debug', 'баг',
            'функция', 'метод', 'класс', 'переменная', 'цикл', 'условие',
            'python', 'import', 'def', 'class', 'if', 'for', 'while',
            'синтаксис', 'алгоритм', 'программа', 'скрипт'
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in code_keywords)

    def create_widgets(self):
        """Создание основного интерфейса"""
        # Настройка стилей
        style = ttk.Style(self)
        style.theme_use("clam")

        # Стили для вкладок
        style.configure("Custom.TNotebook",
                        background=self.colors["bg"],
                        borderwidth=0,
                        tabmargins=0)

        style.configure("Custom.TNotebook.Tab",
                        font=("Segoe UI", 9),
                        padding=8,
                        background=self.colors["tab_bg"],
                        foreground="#d4d4d4",
                        borderwidth=1)

        style.map("Custom.TNotebook.Tab",
                  background=[("selected", self.colors["tab_active"]),
                              ("active", self.colors["btn_hover"])],
                  foreground=[("selected", "#ffffff")])

        # Главная панель с тремя секциями
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Левая панель - проводник проекта
        self.left_frame = tk.Frame(main_pane, bg=self.colors["bg"], width=250)
        main_pane.add(self.left_frame, weight=0)

        # Проводник проекта
        self.project_explorer = ProjectExplorer(self.left_frame, self)

        # Центральная панель - редактор
        self.create_editor_panel(main_pane)

        # Правая панель - инструменты
        self.create_right_panel(main_pane)

        # Инициализация
        self.file_tabs = []
        self.file_editors = []
        self.new_file()

        # Горячие клавиши
        self.bind_hotkeys()

    def create_editor_panel(self, parent):
        """Создание панели редактора"""
        editor_frame = tk.Frame(parent, bg=self.colors["bg"])
        parent.add(editor_frame, weight=5)

        # Панель инструментов редактора
        toolbar = tk.Frame(editor_frame, bg=self.colors["bg"], height=35)
        toolbar.pack(fill=tk.X, pady=(0, 2))
        toolbar.pack_propagate(False)

        # Кнопки быстрого доступа
        tk.Button(toolbar, text="▶", command=self.run_code,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="⏹", command=self.stop_execution,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🔍", command=self.show_find_replace,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="📋", command=self.format_code,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)

        # Информация о файле
        self.file_info_label = tk.Label(toolbar, text="", bg=self.colors["bg"], fg="#858585")
        self.file_info_label.pack(side=tk.RIGHT, padx=10)

        # Notebook для файлов
        self.file_notebook = ttk.Notebook(editor_frame, style="Custom.TNotebook")
        self.file_notebook.pack(fill=tk.BOTH, expand=True)
        self.file_notebook.bind(">", self.switch_file_tab)
        self.file_notebook.bind("", self.show_tab_context_menu)

    def create_right_panel(self, parent):
        """Создание правой панели с инструментами"""
        right_frame = tk.Frame(parent, bg=self.colors["bg"])
        parent.add(right_frame, weight=2)

        # Notebook для инструментов
        self.tools_notebook = ttk.Notebook(right_frame, style="Custom.TNotebook")
        self.tools_notebook.pack(fill=tk.BOTH, expand=True)

        # Создание вкладок
        self.create_problems_tab()
        self.create_debugger_tab()
        self.create_cmd_tab()
        self.create_git_tab()

    def create_problems_tab(self):
        """Создание вкладки проблем (ошибки и предупреждения)"""
        problems_frame = tk.Frame(self.tools_notebook, bg=self.colors["debugger_bg"])
        self.tools_notebook.add(problems_frame, text="Проблемы")

        # Заголовок
        header = tk.Frame(problems_frame, bg=self.colors["debugger_bg"], height=35)
        header.pack(fill=tk.X, pady=(5, 0))
        header.pack_propagate(False)

        title = tk.Label(header, text="Проблемы кода",
                         bg=self.colors["debugger_bg"], fg="#d4d4d4",
                         font=("Segoe UI", 10, "bold"))
        title.pack(side=tk.LEFT, padx=10, pady=8)

        # Список проблем
        self.problems_tree = ttk.Treeview(problems_frame, columns=("file", "line", "message"), show="tree headings")
        self.problems_tree.heading("#0", text="Тип")
        self.problems_tree.heading("file", text="Файл")
        self.problems_tree.heading("line", text="Строка")
        self.problems_tree.heading("message", text="Сообщение")

        self.problems_tree.column("#0", width=50)
        self.problems_tree.column("file", width=100)
        self.problems_tree.column("line", width=50)
        self.problems_tree.column("message", width=300)

        self.problems_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.problems_tree.bind('', self.goto_problem)

    def create_debugger_tab(self):
        """Создание вкладки отладчика"""
        debugger_frame = tk.Frame(self.tools_notebook, bg=self.colors["debugger_bg"])
        self.tools_notebook.add(debugger_frame, text="Отладчик")

        # Заголовок отладчика
        debug_header = tk.Frame(debugger_frame, bg=self.colors["debugger_bg"], height=40)
        debug_header.pack(fill=tk.X, pady=(8, 0))
        debug_header.pack_propagate(False)

        debug_title = tk.Label(debug_header, text="Консоль отладки",
                               bg=self.colors["debugger_bg"], fg="#d4d4d4",
                               font=("Segoe UI", 10, "bold"))
        debug_title.pack(side=tk.LEFT, padx=12, pady=10)

        # Кнопка очистки
        clear_btn = tk.Button(debug_header, text="Очистить",
                              bg=self.colors["btn_danger"], fg="#ffffff",
                              font=("Segoe UI", 8),
                              relief="flat", borderwidth=0,
                              command=self.clear_debugger)
        clear_btn.pack(side=tk.RIGHT, padx=12, pady=8)

        # Область вывода отладчика
        self.debugger = scrolledtext.ScrolledText(
            debugger_frame,
            bg=self.colors["debugger_bg"],
            fg=self.colors["debugger_fg"],
            font=("Consolas", 9),
            insertbackground=self.colors["debugger_fg"],
            selectbackground="#264f78",
            relief="flat",
            padx=12, pady=8,
            state="disabled"
        )
        self.debugger.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        global output
        output = self.output

        # Приветственные сообщения
        self._debugger_insert("=" * 60 + "\n")
        self._debugger_insert("T-Code Professional IDE v2.0\n")
        self._debugger_insert("Система отладки инициализирована\n")
        self._debugger_insert("=" * 60 + "\n\n")

    def create_cmd_tab(self):
        """Создание вкладки командной строки"""
        cmd_frame = tk.Frame(self.tools_notebook, bg=self.colors["cmd_bg"])
        self.tools_notebook.add(cmd_frame, text="Терминал")

        # Заголовок терминала
        cmd_header = tk.Frame(cmd_frame, bg=self.colors["cmd_bg"], height=40)
        cmd_header.pack(fill=tk.X, pady=(8, 0))
        cmd_header.pack_propagate(False)

        cmd_title = tk.Label(cmd_header, text="Интегрированный терминал",
                             bg=self.colors["cmd_bg"], fg=self.colors["cmd_fg"],
                             font=("Segoe UI", 10, "bold"))
        cmd_title.pack(side=tk.LEFT, padx=12, pady=10)

        # Кнопки терминала
        tk.Button(cmd_header, text="Очистить", command=self.clear_cmd,
                  bg=self.colors["btn_danger"], fg="#ffffff", font=("Segoe UI", 8),
                  relief="flat", borderwidth=0).pack(side=tk.RIGHT, padx=(0, 12), pady=8)

        tk.Button(cmd_header, text="Новый терминал", command=self.new_terminal,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", font=("Segoe UI", 8),
                  relief="flat", borderwidth=0).pack(side=tk.RIGHT, padx=5, pady=8)

        # Область вывода команд
        self.cmd_output = scrolledtext.ScrolledText(
            cmd_frame,
            bg=self.colors["cmd_bg"],
            fg=self.colors["cmd_fg"],
            font=("Consolas", 9),
            insertbackground=self.colors["cmd_fg"],
            selectbackground="#264f78",
            relief="flat",
            state="disabled",
            padx=12, pady=8
        )
        self.cmd_output.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        # Панель ввода команд
        cmd_input_frame = tk.Frame(cmd_frame, bg=self.colors["cmd_bg"], height=45)
        cmd_input_frame.pack(fill=tk.X, padx=8, pady=8)
        cmd_input_frame.pack_propagate(False)

        # Промпт
        cmd_prompt = tk.Label(cmd_input_frame, text="T-Code>",
                              bg=self.colors["cmd_bg"], fg=self.colors["cmd_fg"],
                              font=("Consolas", 10, "bold"))
        cmd_prompt.pack(side=tk.LEFT, padx=(8, 8), pady=12)

        # Поле ввода команд
        self.cmd_entry = tk.Entry(cmd_input_frame,
                                  bg=self.colors["input_bg"], fg=self.colors["cmd_fg"],
                                  font=("Consolas", 10),
                                  insertbackground=self.colors["cmd_fg"],
                                  relief="flat", borderwidth=1,
                                  highlightthickness=1,
                                  highlightcolor=self.colors["tab_active"])
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=10, padx=(0, 8))
        self.cmd_entry.bind("", self.process_cmd)
        self.cmd_entry.bind("", self.cmd_history_up)
        self.cmd_entry.bind("", self.cmd_history_down)

        # История команд
        self.cmd_history = []
        self.cmd_history_index = -1

        # Приветствие в терминале
        self._cmd_insert("T-Code Professional Terminal v2.0\n")
        self._cmd_insert("Введите команду и нажмите Enter\n")
        self._cmd_insert("Поддерживаются Python команды и системные команды\n\n")

    def create_git_tab(self):
        """Создание вкладки Git"""
        git_frame = tk.Frame(self.tools_notebook, bg=self.colors["debugger_bg"])
        self.tools_notebook.add(git_frame, text="Git")

        # Заголовок
        header = tk.Frame(git_frame, bg=self.colors["debugger_bg"], height=35)
        header.pack(fill=tk.X, pady=(5, 0))
        header.pack_propagate(False)

        title = tk.Label(header, text="Система контроля версий",
                         bg=self.colors["debugger_bg"], fg="#d4d4d4",
                         font=("Segoe UI", 10, "bold"))
        title.pack(side=tk.LEFT, padx=10, pady=8)

        # Кнопки Git
        button_frame = tk.Frame(git_frame, bg=self.colors["debugger_bg"])
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(button_frame, text="Git Status", command=self.git_status,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Git Add", command=self.git_add,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Git Commit", command=self.git_commit,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", relief="flat").pack(side=tk.LEFT, padx=2)

        # Область вывода Git
        self.git_output = scrolledtext.ScrolledText(
            git_frame,
            bg=self.colors["debugger_bg"],
            fg=self.colors["debugger_fg"],
            font=("Consolas", 9),
            state="disabled",
            relief="flat",
            padx=10, pady=5
        )
        self.git_output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def init_enhanced_ai_agent(self):
        """Инициализация ИИ-агента"""
        ai_frame = tk.Frame(self.tools_notebook, bg=self.colors["chat_bg"])
        self.tools_notebook.add(ai_frame, text="ИИ Помощник")

        # Заголовок ИИ
        ai_header = tk.Frame(ai_frame, bg=self.colors["chat_bg"], height=45)
        ai_header.pack(fill=tk.X, pady=(8, 0))
        ai_header.pack_propagate(False)

        ai_title = tk.Label(ai_header, text="ИИ Помощник (TinyLlama)",
                            bg=self.colors["chat_bg"], fg="#d4d4d4",
                            font=("Segoe UI", 11, "bold"))
        ai_title.pack(side=tk.LEFT, padx=12, pady=12)

        # Индикатор статуса
        self.status_label = tk.Label(ai_header, text="Готов",
                                     bg=self.colors["chat_bg"], fg="#4ec9b0",
                                     font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side=tk.RIGHT, padx=12, pady=12)

        # Панель управления чатом
        control_frame = tk.Frame(ai_frame, bg=self.colors["chat_bg"], height=40)
        control_frame.pack(fill=tk.X, pady=(0, 8))
        control_frame.pack_propagate(False)

        # Кнопки управления
        tk.Button(control_frame, text="Очистить чат", command=self.clear_chat,
                  bg=self.colors["btn_danger"], fg="#ffffff", font=("Segoe UI", 8),
                  relief="flat", borderwidth=0).pack(side=tk.LEFT, padx=12, pady=8)

        tk.Button(control_frame, text="Анализ кода", command=self.analyze_current_code,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", font=("Segoe UI", 8),
                  relief="flat", borderwidth=0).pack(side=tk.LEFT, padx=8, pady=8)

        tk.Button(control_frame, text="Объяснить", command=self.explain_code,
                  bg=self.colors["btn_normal"], fg="#d4d4d4", font=("Segoe UI", 8),
                  relief="flat", borderwidth=0).pack(side=tk.LEFT, padx=8, pady=8)

        # Область чата
        chat_container = tk.Frame(ai_frame, bg=self.colors["chat_bg"])
        chat_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Область отображения сообщений
        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap='word',
            bg=self.colors["debugger_bg"],
            fg="#d4d4d4",
            font=("Segoe UI", 10),
            state="disabled",
            relief="flat",
            padx=12, pady=12
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Настройка тегов для форматирования
        self.setup_chat_tags()

        # Панель ввода
        input_container = tk.Frame(chat_container, bg=self.colors["chat_bg"])
        input_container.pack(fill=tk.X, side=tk.BOTTOM)

        # Поле ввода сообщения
        self.ai_input = tk.Text(
            input_container,
            height=3,
            bg=self.colors["input_bg"],
            fg="#d4d4d4",
            font=("Segoe UI", 10),
            insertbackground="#d4d4d4",
            relief="flat",
            wrap='word',
            padx=12, pady=10,
            borderwidth=1,
            highlightthickness=1,
            highlightcolor=self.colors["tab_active"]
        )
        self.ai_input.pack(fill=tk.X, pady=(0, 12))

        # Панель кнопок
        button_container = tk.Frame(input_container, bg=self.colors["chat_bg"])
        button_container.pack(fill=tk.X)

        # Кнопка отправки
        self.send_button = tk.Button(
            button_container,
            text="Отправить",
            bg=self.colors["btn_normal"],
            fg="#d4d4d4",
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
            padx=20, pady=10,
            command=self.start_ai_query,
            cursor="hand2"
        )
        self.send_button.pack(side=tk.RIGHT, padx=(8, 0))

        # Кнопка отмены
        self.cancel_button = tk.Button(
            button_container,
            text="Отмена",
            bg=self.colors["btn_danger"],
            fg="#ffffff",
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
            padx=20, pady=10,
            command=self.cancel_ai_request,
            cursor="hand2",
            state="disabled"
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

        # Привязка клавиш
        self.ai_input.bind("", lambda e: self.start_ai_query())
        self.ai_input.bind("", lambda e: None)

        # Приветственные сообщения
        self.add_system_message("ИИ Помощник инициализирован")
        self.add_system_message("Доступные команды: анализ кода, объяснение, улучшения")

    def setup_chat_tags(self):
        """Настройка тегов для форматирования чата"""
        self.chat_display.tag_configure("user",
                                        foreground=self.colors["user_msg"],
                                        font=("Segoe UI", 10, "bold"))

        self.chat_display.tag_configure("ai",
                                        foreground=self.colors["ai_msg"],
                                        font=("Segoe UI", 10, "bold"))

        self.chat_display.tag_configure("system",
                                        foreground=self.colors["system_msg"],
                                        font=("Segoe UI", 9, "bold"))

        self.chat_display.tag_configure("error",
                                        foreground=self.colors["error_msg"],
                                        font=("Segoe UI", 10, "bold"))

        self.chat_display.tag_configure("code",
                                        background=self.colors["code_bg"],
                                        foreground="#f8f8f2",
                                        font=("Consolas", 9),
                                        relief="solid",
                                        borderwidth=1)

        self.chat_display.tag_configure("timestamp",
                                        foreground="#6a9955",
                                        font=("Segoe UI", 8))

    # === Новые методы для профессиональных функций ===

    def open_folder(self):
        """Открыть папку проекта"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.project_explorer.load_directory(folder_path)
            self.project_explorer.current_path = folder_path

    def open_file_from_explorer(self, file_path):
        """Открыть файл из проводника"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Проверяем, не открыт ли уже этот файл
            for i, tab in enumerate(self.file_tabs):
                if tab.path == file_path:
                    self.file_notebook.select(i)
                    return

            # Создаем новую вкладку
            tab = FileTab(name=os.path.basename(file_path), content=content, path=file_path)
            self.create_editor_tab(tab, content)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}")

    def save_file_as(self):
        """Сохранить файл как"""
        try:
            tab, input_text, _ = self.get_current_editor()

            filetypes = [
                ("Python files", "*.py"),
                ("T-Code files", "*.tcd"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]

            filepath = filedialog.asksaveasfilename(defaultextension=".py", filetypes=filetypes)
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(input_text.get("1.0", tk.END))

                tab.path = filepath
                tab.name = os.path.basename(filepath)
                tab.saved = True

                # Обновляем название вкладки
                current_tab = self.file_notebook.select()
                self.file_notebook.tab(current_tab, text=tab.name)

                self.add_system_message(f"Файл сохранен как: {os.path.basename(filepath)}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")

    def save_all_files(self):
        """Сохранить все открытые файлы"""
        saved_count = 0
        for i, tab in enumerate(self.file_tabs):
            if not tab.saved and tab.path:
                try:
                    _, editor, _ = self.get_editor_by_index(i)
                    with open(tab.path, 'w', encoding='utf-8') as f:
                        f.write(editor.get("1.0", tk.END))
                    tab.saved = True
                    saved_count += 1
                except Exception:
                    pass

        if saved_count > 0:
            self.add_system_message(f"Сохранено файлов: {saved_count}")

    def close_current_file(self):
        """Закрыть текущий файл"""
        if len(self.file_tabs) > 1:
            current_index = self.file_notebook.index(self.file_notebook.select())
            self.close_file_tab(current_index)

    def redo(self):
        """Повторить отмененное действие"""
        try:
            _, input_text, _ = self.get_current_editor()
            input_text.edit_redo()
        except Exception:
            pass

    def cut(self):
        """Вырезать выделенный текст"""
        try:
            _, input_text, _ = self.get_current_editor()
            input_text.event_generate(">")
        except Exception:
            pass

    def copy(self):
        """Копировать выделенный текст"""
        try:
            _, input_text, _ = self.get_current_editor()
            input_text.event_generate(">")
        except Exception:
            pass

    def paste(self):
        """Вставить текст из буфера"""
        try:
            _, input_text, _ = self.get_current_editor()
            input_text.event_generate(">")
        except Exception:
            pass

    