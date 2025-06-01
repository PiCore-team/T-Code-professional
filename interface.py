import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
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
        self.text_widget.bind('<KeyRelease>', self.redraw)
        self.text_widget.bind('<Button-1>', self.redraw)
        self.text_widget.bind('<MouseWheel>', self.redraw)
        self.text_widget.bind('<Configure>', self.redraw)

        self.cmd_running = False

        # Привязка прокрутки
        self.text_widget.bind('<B1-Motion>', self.redraw)

    def redraw(self, event=None):
        """Перерисовка номеров строк"""
        self.delete("all")

        # Получаем первую видимую строку
        first_line = self.text_widget.index("@0,0")

        # Получаем информацию о видимых строках
        line_num = int(first_line.split('.')[0])

        # Рисуем номера для всех видимых строк
        y_pos = 0
        while True:
            try:
                # Получаем информацию о строке
                dline_info = self.text_widget.dlineinfo(f"{line_num}.0")
                if dline_info is None:
                    break

                # Позиция строки относительно виджета
                line_y = dline_info[1]

                # Рисуем номер строки
                self.create_text(
                    45, line_y + 10,  # Выравнивание по правому краю
                    anchor="e",
                    text=str(line_num),
                    fill="#858585",
                    font=("Consolas", 10)
                )

                line_num += 1

                # Проверяем, не вышли ли за пределы видимой области
                if line_y > self.text_widget.winfo_height():
                    break

            except tk.TclError:
                break

        # Планируем следующую перерисовку через небольшую задержку
        self.after_idle(self.sync_scroll)

    def sync_scroll(self):
        """Синхронизация прокрутки с текстовым виджетом"""
        # Получаем текущую позицию прокрутки
        try:
            top, bottom = self.text_widget.yview()
            # Обновляем область прокрутки canvas
            self.configure(scrollregion=self.bbox("all"))
        except:
            pass


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


class CodeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("T-Code Professional")
        self.geometry("1400x800")
        self.configure(bg="#121212")

        # Инициализация атрибутов
        self.cmd_running = False  # Флаг выполнения команды
        self.chat_messages = []
        self.ai_request_manager = AIRequestManager(self._handle_ai_response)

        # Темная цветовая схема
        self.colors = {
            "bg": "#1B1C1E",
            "editor_bg": "#232324",
            "editor_fg": "#d4d4d4",
            "line_numbers": "#2d2d2d",
            "tab_bg": "#1E1E1E",
            "tab_active": "#8ebbda",
            "btn_normal": "#3a3d41",
            "btn_hover": "#4D5156",
            "btn_danger": "#db576d",
            "debugger_bg": "#1d2024",
            "debugger_fg": "#d4d4d4",
            "cmd_bg": "#212721",
            "cmd_fg": "#b1dea8",
            "user_msg": "#9cdcfe",
            "ai_msg": "#ce9178",
            "system_msg": "#dcdcaa",
            "error_msg": "#f44747",
            "code_bg": "#1e1e1e",
            "chat_bg": "#222226",
            "input_bg": "#2d2d2d",
            "border": "#3e3e42"
        }

        # Инициализация компонентов
        self.create_menu()
        self.create_widgets()
        self.init_enhanced_ai_agent()

    def create_menu(self):
        """Создание классического верхнего меню"""
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
        file_menu.add_command(label="Сохранить", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.quit)

        # Меню "Правка"
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Отменить", command=self.undo, accelerator="Ctrl+Z")

        # Меню "Выполнение"
        run_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                           activebackground=self.colors["btn_hover"],
                           activeforeground="#ffffff")
        menubar.add_cascade(label="Выполнение", menu=run_menu)
        run_menu.add_command(label="Запустить код", command=self.run_code, accelerator="F5")

        # Меню "ИИ"
        ai_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                          activebackground=self.colors["btn_hover"],
                          activeforeground="#ffffff")
        menubar.add_cascade(label="ИИ", menu=ai_menu)
        ai_menu.add_command(label="Анализ кода", command=self.quick_ai_analysis)
        ai_menu.add_command(label="Очистить чат", command=self.clear_chat)

        # Меню "Вид"
        view_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="Очистить отладчик", command=self.clear_debugger)
        view_menu.add_command(label="Очистить терминал", command=self.clear_cmd)

        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.colors["bg"], fg="#d4d4d4",
                            activebackground=self.colors["btn_hover"],
                            activeforeground="#ffffff")
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Справка", command=self.open_help, accelerator="F1")
        help_menu.add_command(label="Настройки", command=self.setings)

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

        # Главная панель
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Центральная панель редактора
        self.create_editor_panel(main_pane)

        # Правая панель с инструментами
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

        # Заголовок редактора
        header_frame = tk.Frame(editor_frame, bg=self.colors["bg"], height=35)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        header_frame.pack_propagate(False)

        editor_title = tk.Label(header_frame, text="Редактор кода",
                                bg=self.colors["bg"], fg="#d4d4d4",
                                font=("Segoe UI", 11, "bold"))
        editor_title.pack(side=tk.LEFT, pady=8)

        # Notebook для файлов
        self.file_notebook = ttk.Notebook(editor_frame, style="Custom.TNotebook")
        self.file_notebook.pack(fill=tk.BOTH, expand=True)
        self.file_notebook.bind("<<NotebookTabChanged>>", self.switch_file_tab)

    def create_right_panel(self, parent):
        """Создание правой панели с инструментами"""
        right_frame = tk.Frame(parent, bg=self.colors["bg"])
        parent.add(right_frame, weight=3)

        # Заголовок правой панели
        header_frame = tk.Frame(right_frame, bg=self.colors["bg"], height=35)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        header_frame.pack_propagate(False)

        panel_title = tk.Label(header_frame, text="Панель инструментов",
                               bg=self.colors["bg"], fg="#d4d4d4",
                               font=("Segoe UI", 11, "bold"))
        panel_title.pack(side=tk.LEFT, pady=8)

        # Notebook для инструментов
        self.tools_notebook = ttk.Notebook(right_frame, style="Custom.TNotebook")
        self.tools_notebook.pack(fill=tk.BOTH, expand=True)

        # Создание вкладок
        self.create_view_tab()
        self.create_debugger_tab()
        self.create_cmd_tab()

    def create_view_tab(self):
        """Создание вкладки просмотра"""
        view_frame = tk.Frame(self.tools_notebook, bg=self.colors["editor_bg"])
        self.tools_notebook.add(view_frame, text="Просмотр")

        # Содержимое вкладки просмотра
        view_label = tk.Label(view_frame, text="Область предварительного просмотра",
                              bg=self.colors["editor_bg"], fg="#d4d4d4",
                              font=("Segoe UI", 10))
        view_label.pack(expand=True)

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
        self._debugger_insert("=" * 50 + "\n")
        self._debugger_insert("T-Code Professional v1.0\n")
        self._debugger_insert("Система отладки инициализирована\n")
        self._debugger_insert("=" * 50 + "\n\n")

    def create_cmd_tab(self):
        """Создание вкладки командной строки"""
        cmd_frame = tk.Frame(self.tools_notebook, bg=self.colors["cmd_bg"])
        self.tools_notebook.add(cmd_frame, text="Терминал")

        # Заголовок терминала
        cmd_header = tk.Frame(cmd_frame, bg=self.colors["cmd_bg"], height=40)
        cmd_header.pack(fill=tk.X, pady=(8, 0))
        cmd_header.pack_propagate(False)

        cmd_title = tk.Label(cmd_header, text="Командная строка",
                             bg=self.colors["cmd_bg"], fg=self.colors["cmd_fg"],
                             font=("Segoe UI", 10, "bold"))
        cmd_title.pack(side=tk.LEFT, padx=12, pady=10)

        # Кнопка очистки терминала
        clear_cmd_btn = tk.Button(cmd_header, text="Очистить",
                                  bg=self.colors["btn_danger"], fg="#ffffff",
                                  font=("Segoe UI", 8),
                                  relief="flat", borderwidth=0,
                                  command=self.clear_cmd)
        clear_cmd_btn.pack(side=tk.RIGHT, padx=12, pady=8)

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

        # Кнопка прерывания команды
        self.kill_button = tk.Button(
            cmd_input_frame,
            text="Прервать",
            bg=self.colors["btn_danger"],
            fg="#ffffff",
            font=("Segoe UI", 8),
            relief="flat",
            borderwidth=0,
            command=self.kill_command,
            state="disabled"
        )
        self.kill_button.pack(side=tk.RIGHT, padx=(0, 8), pady=10)

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
        self.cmd_entry.bind("<Return>", self.process_cmd)

        # Приветствие в терминале
        self._cmd_insert("T-Code Terminal v1.0\n")
        self._cmd_insert("Введите команду и нажмите Enter\n")
        self._cmd_insert("Используйте 'cmd' перед системными командами (например: cmd pip install numpy)\n")
        self._cmd_insert("Для прерывания длительной команды нажмите кнопку 'Прервать'\n\n")



    def update_kill_button(self):
        """Обновляет состояние кнопки прерывания"""
        if self.cmd_running:
            self.kill_button.config(state="normal")
        else:
            self.kill_button.config(state="disabled")

    def kill_command(self):
        """Прерывает выполнение текущей команды"""
        try:
            # Вызываем команду прерывания
            result = cmd.compile("cmd_kill")
            self._cmd_insert(f"{result}\n\n")
        except Exception as e:
            self._cmd_insert(f"Ошибка прерывания: {str(e)}\n\n")
        finally:
            self.cmd_running = False
            self.update_kill_button()




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
        clear_chat_btn = tk.Button(control_frame, text="Очистить чат",
                                   bg=self.colors["btn_danger"], fg="#ffffff",
                                   font=("Segoe UI", 8),
                                   relief="flat", borderwidth=0,
                                   command=self.clear_chat)
        clear_chat_btn.pack(side=tk.LEFT, padx=12, pady=8)

        analyze_btn = tk.Button(control_frame, text="Анализ кода",
                                bg=self.colors["btn_normal"], fg="#d4d4d4",
                                font=("Segoe UI", 8),
                                relief="flat", borderwidth=0,
                                command=self.analyze_current_code)
        analyze_btn.pack(side=tk.LEFT, padx=8, pady=8)

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
        self.ai_input.bind("<Control-Return>", lambda e: self.start_ai_query())
        self.ai_input.bind("<Shift-Return>", lambda e: None)

        # Приветственные сообщения
        self.add_system_message("ИИ Помощник инициализирован")
        self.add_system_message("Используйте Ctrl+Enter для отправки сообщения")

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

    def add_message(self, sender, content, message_type="text"):
        """Добавление сообщения в чат"""
        message = ChatMessage(sender, content, message_type=message_type)
        self.chat_messages.append(message)

        self.chat_display.config(state="normal")

        # Временная метка
        timestamp = message.timestamp.strftime("%H:%M:%S")
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")

        # Отправитель
        if sender == "user":
            self.chat_display.insert(tk.END, "Вы: ", "user")
        elif sender == "ai":
            self.chat_display.insert(tk.END, "ИИ: ", "ai")
        elif sender == "system":
            self.chat_display.insert(tk.END, "Система: ", "system")
        elif sender == "error":
            self.chat_display.insert(tk.END, "Ошибка: ", "error")

        # Обработка содержимого
        if message_type == "code":
            self.process_code_message(content)
        else:
            self.process_text_message(content)

        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def process_text_message(self, content):
        """Обработка текстового сообщения с поддержкой кода"""
        # Поиск блоков кода
        code_pattern = r'``````'
        parts = re.split(code_pattern, content, flags=re.DOTALL)

        for i, part in enumerate(parts):
            if i % 2 == 0:  # Обычный текст
                self.chat_display.insert(tk.END, part)
            else:  # Код
                self.insert_code_block(part)

    def process_code_message(self, content):
        """Обработка сообщения с кодом"""
        self.insert_code_block(content)

    def insert_code_block(self, code):
        """Вставка блока кода с кнопкой копирования"""
        self.chat_display.insert(tk.END, "\n")

        # Заголовок блока кода
        self.chat_display.insert(tk.END, "Код Python:", "system")
        self.chat_display.insert(tk.END, "\n")

        # Код
        self.chat_display.insert(tk.END, code, "code")
        self.chat_display.insert(tk.END, "\n")

        # Кнопка копирования
        copy_btn = tk.Button(
            self.chat_display,
            text="Копировать код",
            font=("Segoe UI", 8),
            bg=self.colors["btn_normal"],
            fg="#d4d4d4",
            relief="flat",
            borderwidth=0,
            padx=10, pady=6,
            command=lambda: self.copy_code_to_clipboard(code),
            cursor="hand2"
        )

        self.chat_display.window_create(tk.INSERT, window=copy_btn)

    def add_system_message(self, content):
        """Добавление системного сообщения"""
        self.add_message("system", content)

    def copy_code_to_clipboard(self, code):
        """Копирование кода в буфер обмена"""
        self.clipboard_clear()
        self.clipboard_append(code.strip())
        self.add_system_message("Код скопирован в буфер обмена")

    def clear_chat(self):
        """Очистка чата"""
        self.chat_messages.clear()
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state="disabled")
        self.add_system_message("Чат очищен")

    def start_ai_query(self, context_code=None):
        """Упрощенный запрос к ИИ"""
        user_input = self.ai_input.get("1.0", "end-1c").strip()
        if not user_input:
            return

        if self.ai_request_manager.is_processing:
            self.add_system_message("Дождитесь завершения предыдущего запроса")
            return

        # Очистка поля ввода
        self.ai_input.delete("1.0", tk.END)

        # Добавление сообщения пользователя
        self.add_message("user", user_input)

        # Получение контекста кода
        context = context_code if context_code else ""

        # Всегда пытаемся получить код из редактора
        try:
            tab, editor, _ = self.get_current_editor()
            current_code = editor.get("1.0", "end-1c").strip()
            if current_code:
                context = current_code
        except Exception:
            pass

        # Обновление интерфейса
        self.update_ui_for_processing(True)

        # Запуск запроса
        success = self.ai_request_manager.add_request(user_input, context)
        if not success:
            self.add_message("error", "Не удалось запустить запрос")
            self.update_ui_for_processing(False)

    def analyze_current_code(self):
        """Анализ текущего кода"""
        try:
            tab, editor, _ = self.get_current_editor()
            current_code = editor.get("1.0", "end-1c").strip()

            if not current_code:
                self.add_system_message("Нет кода для анализа")
                return

            # Переключение на вкладку ИИ
            for i in range(self.tools_notebook.index("end")):
                tab_text = self.tools_notebook.tab(i, "text")
                if "ИИ" in tab_text:
                    self.tools_notebook.select(i)
                    break

            # Формирование запроса для анализа
            analysis_prompt = "Проанализируй код и найди ошибки"

            # Добавление в поле ввода
            self.ai_input.delete("1.0", tk.END)
            self.ai_input.insert("1.0", analysis_prompt)

            # Запуск анализа
            self.start_ai_query(context_code=current_code)

        except Exception as e:
            self.add_message("error", f"Ошибка при получении кода: {e}")

    def quick_ai_analysis(self):
        """Быстрый анализ кода через меню"""
        self.analyze_current_code()

    def cancel_ai_request(self):
        """Отмена текущего запроса"""
        self.ai_request_manager.cancel_request()
        self.update_ui_for_processing(False)
        self.add_system_message("Запрос отменен")

    def update_ui_for_processing(self, is_processing):
        """Обновление интерфейса во время обработки"""
        if is_processing:
            self.send_button.config(state="disabled", text="Обработка...")
            self.cancel_button.config(state="normal")
            self.status_label.config(text="Обработка...", fg="#ffd700")
        else:
            self.send_button.config(state="normal", text="Отправить")
            self.cancel_button.config(state="disabled")
            self.status_label.config(text="Готов", fg="#4ec9b0")

    def _handle_ai_response(self, status, response):
        """Обработка ответа от ИИ"""

        def update_ui():
            if status == "success":
                if response.strip():
                    cleaned_response = process_content(response)
                    self.add_message("ai", cleaned_response)
                else:
                    self.add_message("ai", "Не удалось сгенерировать ответ")
            else:
                self.add_message("error", f"Ошибка запроса: {response}")

            self.update_ui_for_processing(False)

        self.after(0, update_ui)

    # === Методы для работы с файлами и редактором ===

    def bind_hotkeys(self):
        """Привязка горячих клавиш"""
        self.bind_all("<Control-n>", lambda e: self.new_file())
        self.bind_all("<Control-o>", lambda e: self.load_file())
        self.bind_all("<Control-s>", lambda e: self.save_file())
        self.bind_all("<Control-z>", self.undo)
        self.bind("<F5>", lambda e: self.run_code())
        self.bind("<F1>", lambda e: self.open_help())

    def clear_debugger(self):
        """Очистка отладчика"""
        self.debugger.config(state="normal")
        self.debugger.delete("1.0", tk.END)
        self.debugger.config(state="disabled")
        self._debugger_insert("Отладчик очищен\n\n")

    def clear_cmd(self):
        """Очистка терминала"""
        self.cmd_output.config(state="normal")
        self.cmd_output.delete("1.0", tk.END)
        self.cmd_output.config(state="disabled")
        self._cmd_insert("Терминал очищен\n\n")

    def _cmd_insert(self, text):
        """Вставка текста в терминал"""
        self.cmd_output.config(state="normal")
        self.cmd_output.insert(tk.END, str(text))
        self.cmd_output.see(tk.END)
        self.cmd_output.config(state="disabled")

    def setings(self):
        """Окно настроек"""
        settings_window = tk.Toplevel(self)
        settings_window.title("Настройки")
        settings_window.geometry("400x300")
        settings_window.configure(bg=self.colors["bg"])
        settings_window.resizable(False, False)

        settings_window.transient(self)
        settings_window.grab_set()

        title_label = tk.Label(settings_window,
                               text="Настройки приложения",
                               bg=self.colors["bg"],
                               fg="#d4d4d4",
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=20)

        ai_frame = tk.LabelFrame(settings_window,
                                 text="Настройки ИИ",
                                 bg=self.colors["bg"],
                                 fg="#d4d4d4",
                                 font=("Segoe UI", 10, "bold"))
        ai_frame.pack(padx=20, pady=10, fill=tk.X)

        model_label = tk.Label(ai_frame,
                               text=f"Текущая модель: {MODEL}",
                               bg=self.colors["bg"],
                               fg="#d4d4d4")
        model_label.pack(pady=5)

    def insert_spaces(self, event=None):
        widget = event.widget
        widget.insert(tk.INSERT, '    ')
        return "break"

    def auto_indent(self, event):
        widget = event.widget
        index = widget.index("insert linestart")
        prev_line = widget.get(f"{index} -1l linestart", f"{index} -1l lineend")
        indent = re.match(r"^(\s*)", prev_line).group(1)

        if prev_line.rstrip().endswith(":"):
            indent += "    "

        widget.insert("insert", f"\n{indent}")
        return "break"

    def highlight_syntax(self, event=None):
        try:
            _, input_text, _ = self.get_current_editor()
        except Exception:
            return

        code = input_text.get("1.0", "end-1c")

        for tag in input_text.tag_names():
            input_text.tag_remove(tag, "1.0", "end")

        # Ключевые слова Python
        arguments = r"\b(self|get)\b"
        symbols = r"\b(neural|layer|PiCore|delta|var)\b"
        important = r"\b(import|from|return|or|not|None|in|is)\b"
        funct = r"\b(print|input|def|if|else|elif|class|for|while)\b"
        keywords = r"\b(False|True|and|as|assert|async|await|break|continue|del|except|finally|range|global|lambda|nonlocal|pass|raise|return|try|with|yield)\b"


        for match in re.finditer(keywords, code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("keyword", start, end)
            input_text.tag_config("keyword", foreground="#6b5aef")

        for match in re.finditer(symbols, code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("symbols", start, end)
            input_text.tag_config("symbols", foreground="#e45b53")

        for match in re.finditer(important, code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("important", start, end)
            input_text.tag_config("important", foreground="#14a5e3")


        for match in re.finditer(funct, code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("funct", start, end)
            input_text.tag_config("funct", foreground="#d69a56")

        # Строки
        for match in re.finditer(r'".*?"|\'.*?\'', code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("string", start, end)
            input_text.tag_config("string", foreground="#9ace78")

        # Комментарии
        for match in re.finditer(r"#.*", code):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            input_text.tag_add("comment", start, end)
            input_text.tag_config("comment", foreground="#696969")

    def new_file(self):
        tab = FileTab()
        frame = tk.Frame(self.file_notebook, bg=self.colors["editor_bg"])

        # Создание редактора с правильными номерами строк
        editor_container = tk.Frame(frame, bg=self.colors["editor_bg"])
        editor_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Текстовый виджет
        input_text = tk.Text(editor_container, wrap='none', undo=True, font=("Consolas", 11),
                             background=self.colors["editor_bg"], foreground=self.colors["editor_fg"],
                             insertbackground="#d4d4d4", selectbackground="#264f78",
                             relief="flat", padx=12, pady=12,
                             borderwidth=0)

        # Номера строк
        line_numbers = LineNumbers(editor_container, input_text)

        # Размещение виджетов
        line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Скроллбар
        scrollbar = tk.Scrollbar(editor_container, orient=tk.VERTICAL, command=input_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        input_text.config(yscrollcommand=scrollbar.set)

        # Привязка событий
        input_text.bind("<Tab>", self.insert_spaces)
        input_text.bind("<Return>", self.auto_indent)
        input_text.bind("<KeyRelease>", self.highlight_syntax)
        input_text.bind("<Button-1>", lambda e: line_numbers.redraw())
        input_text.bind("<MouseWheel>", lambda e: line_numbers.redraw())

        # Добавление вкладки
        tab_text = f"{tab.name}"
        self.file_notebook.add(frame, text=tab_text)
        self.file_tabs.append(tab)
        self.file_editors.append((line_numbers, input_text))
        self.file_notebook.select(len(self.file_tabs) - 1)

        # Инициальная отрисовка номеров строк
        self.after(100, line_numbers.redraw)

    def load_file(self):
        filetypes = [
            ("T-Code files", "*.tcd"),
            ("Python files", "*.py"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]

        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                tab = FileTab(name=os.path.basename(filepath), content=content, path=filepath)
                frame = tk.Frame(self.file_notebook, bg=self.colors["editor_bg"])

                editor_container = tk.Frame(frame, bg=self.colors["editor_bg"])
                editor_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

                # Текстовый виджет
                input_text = tk.Text(editor_container, wrap='none', undo=True, font=("Consolas", 11),
                                     background=self.colors["editor_bg"], foreground=self.colors["editor_fg"],
                                     insertbackground="#d4d4d4", selectbackground="#264f78",
                                     relief="flat", padx=12, pady=12,
                                     borderwidth=0)
                input_text.insert("1.0", content)

                # Номера строк
                line_numbers = LineNumbers(editor_container, input_text)

                # Размещение виджетов
                line_numbers.pack(side=tk.LEFT, fill=tk.Y)
                input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                # Скроллбар
                scrollbar = tk.Scrollbar(editor_container, orient=tk.VERTICAL, command=input_text.yview)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                input_text.config(yscrollcommand=scrollbar.set)

                # Привязка событий
                input_text.bind("<Tab>", self.insert_spaces)
                input_text.bind("<Return>", self.auto_indent)
                input_text.bind("<KeyRelease>", self.highlight_syntax)
                input_text.bind("<Button-1>", lambda e: line_numbers.redraw())
                input_text.bind("<MouseWheel>", lambda e: line_numbers.redraw())

                tab_text = f"{tab.name}"
                self.file_notebook.add(frame, text=tab_text)
                self.file_tabs.append(tab)
                self.file_editors.append((line_numbers, input_text))
                self.file_notebook.select(len(self.file_tabs) - 1)

                self.highlight_syntax()
                self.after(100, line_numbers.redraw)
                self.add_system_message(f"Файл загружен: {os.path.basename(filepath)}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{e}")

    def switch_file_tab(self, event=None):
        try:
            idx = self.file_notebook.index(self.file_notebook.select())
            line_numbers, input_text = self.file_editors[idx]
            self.highlight_syntax()
            line_numbers.redraw()
        except Exception:
            pass

    def get_current_editor(self):
        idx = self.file_notebook.index(self.file_notebook.select())
        return self.file_tabs[idx], self.file_editors[idx][1], self.file_editors[idx][0]

    def output(self, text):
        self._debugger_insert(str(text) + "\n")

    def run_code(self):
        global i
        i += 1
        self._debugger_insert("\n" + "=" * 30 + f" OUTPUT {i} " + "=" * 30 + "\n")

        try:
            _, input_text, _ = self.get_current_editor()
            code = input_text.get("1.0", tk.END).strip()

            if not code:
                self.output("Нет кода для выполнения")
                return

            compiled = c.t_compile(code)
            self.output(compiled)

        except Exception as e:
            self.output(f"Ошибка выполнения: {e}")

        self._debugger_insert("=" * 70 + "\n\n")

    def save_file(self):
        try:
            tab, input_text, _ = self.get_current_editor()

            filetypes = [
                ("T-Code files", "*.tcd"),
                ("Python files", "*.py"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]

            if tab.path is None:
                filepath = filedialog.asksaveasfilename(defaultextension=".tcd", filetypes=filetypes)
                if not filepath:
                    return
                tab.path = filepath
                tab.name = os.path.basename(filepath)

                current_tab = self.file_notebook.select()
                self.file_notebook.tab(current_tab, text=f"{tab.name}")
            else:
                filepath = tab.path

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(input_text.get("1.0", tk.END))

            tab.saved = True
            self.add_system_message(f"Файл сохранен: {os.path.basename(filepath)}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def open_help(self):
        help_window = tk.Toplevel(self)
        help_window.title("Справка")
        help_window.geometry("600x400")
        help_window.configure(bg=self.colors["bg"])

        help_text = scrolledtext.ScrolledText(help_window,
                                              bg=self.colors["debugger_bg"],
                                              fg=self.colors["debugger_fg"],
                                              font=("Segoe UI", 10),
                                              padx=20, pady=20)
        help_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        help_content = """
T-Code Professional - Справка

ГОРЯЧИЕ КЛАВИШИ:
-  Ctrl+N - Новый файл
-  Ctrl+O - Открыть файл  
-  Ctrl+S - Сохранить файл
-  Ctrl+Z - Отменить действие
-  F5 - Запустить код
-  F1 - Справка
-  Ctrl+Enter - Отправить сообщение (асистент)

Если программа запущена первый раз, запустите program_init() во вкладке "Терминал"
Взаимодействовать с командной строкой системы можно с помощью преписки cmd во вкладке "Терминал". Например cmd pip install numpy.

Новые команды- 
Каждая добавленная нами команда должна начинаться с символа !, а так жене может использоваться в класическом python коде, хотяи могут с ним взаимодействовать.
Неправильно-

    var.create(mv, 10)
    #команда начитается не с !

    def func ():
        !var.create(mv, 10)
    #добавленные команды не могут использоваться внтри python кода

Праильно-

    !var.create(mv, 10)
    print(mv)

Полный список команд может быть просмотрен при введении all_comands() в теринале

        """

        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")

    def execute_system_command(self, command):
        """Выполняет системную команду в отдельном потоке"""
        try:
            self.cmd_running = True
            self.after(0, self.update_kill_button)  # Обновляем кнопку прерывания

            # Формируем команду в правильном формате
            formatted_command = f'cmd("{command}")'

            # Выполняем команду через механизм mcmd
            result = cmd.compile(formatted_command)

            # Обновляем интерфейс из основного потока
            self.after(0, lambda: self._cmd_insert(f"{result}\n\n"))

        except Exception as e:
            self.after(0, lambda: self._cmd_insert(f"Ошибка выполнения команды: {str(e)}\n\n"))
        finally:
            self.cmd_running = False
            self.after(0, self.update_kill_button)  # Обновляем кнопку прерывания

    def process_cmd(self, event=None):
        cmd_text = self.cmd_entry.get().strip()
        if not cmd_text:
            return

        self._cmd_insert(f"T-Code> {cmd_text}\n")
        self.cmd_entry.delete(0, tk.END)

        # Если уже выполняется команда - игнорируем новые
        if self.cmd_running:
            self._cmd_insert("Дождитесь завершения текущей команды\n\n")
            return

        try:
            if cmd_text.startswith("cmd "):
                # Запускаем системную команду в отдельном потоке
                threading.Thread(
                    target=self.execute_system_command,
                    args=(cmd_text[4:],),
                    daemon=True
                ).start()
            else:
                # Обработка обычной команды T-Code
                result = cmd.compile(cmd_text)
                self._cmd_insert(f"{result}\n\n")
        except Exception as e:
            self._cmd_insert(f"Ошибка: {e}\n\n")

    def _debugger_insert(self, text):
        self.debugger.config(state="normal")
        self.debugger.insert(tk.END, str(text))
        self.debugger.see(tk.END)
        self.debugger.config(state="disabled")

    def undo(self, event=None):
        try:
            _, input_text, _ = self.get_current_editor()
            input_text.edit_undo()
        except Exception:
            pass


if __name__ == "__main__":
    app = CodeApp()
    app.mainloop()

