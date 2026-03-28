#!/usr/bin/env python3
"""
HeyGen Voice Generator - Desktop Application
Десктопное приложение для генерации голоса через HeyGen API
"""

import os
import re
import sys
import time
import json
import ctypes
import base64
import platform
import requests
import threading
import pyperclip
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
from datetime import datetime
from hotkeys import HotkeyMixin

# Импортируем модуль лицензирования
from license_manager import LicenseManager

# ==================== НАСТРОЙКИ ====================
CHUNK_SIZE = 5000  # Максимальный размер одной части
DELAY = 2  # Задержка между частями
# =================================================

def get_app_dir():
    if sys.platform == "darwin":
        path = os.path.expanduser("~/Library/Application Support/HeyGenVoice")
    elif os.name == "nt":
        path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "HeyGenVoice")
    else:
        path = os.path.expanduser("~/.heygen_voice")

    os.makedirs(path, exist_ok=True)
    return path

def get_resource_dir():
    """Папка с ресурсами (рядом с приложением)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_results_dir():
    """Возвращает папку для результатов"""
    base_dir = get_app_dir()
    results_dir = os.path.join(base_dir, "Результаты")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir

def get_text_dir():
    """Возвращает папку для текстов"""
    base_dir = get_app_dir()
    text_dir = os.path.join(base_dir, "Текст")
    os.makedirs(text_dir, exist_ok=True)
    return text_dir

def resource_path(relative_path):
    """Получить путь к файлу, корректно работающий в собранном exe"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ApiSettingsDialog(HotkeyMixin):
    """Диалог настроек API"""

    def __init__(self, app, config_data=None):
        self.app = app
        self.config_data = config_data or {}
        self.result = None

        # Создаем окно
        self.dialog = tk.Toplevel(app.root)
        self.dialog.title("Настройки")
        self.dialog.geometry("700x650")
        self.dialog.resizable(True, True)
        self.dialog.minsize(500, 500)

        # Центрируем окно с проверкой границ
        self.dialog.transient(app.root)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        window_width = 700
        window_height = 650

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        if y + window_height > screen_height:
            y = max(0, screen_height - window_height - 30)
        if y < 0:
            y = 30
        if x + window_width > screen_width:
            x = max(0, screen_width - window_width - 10)
        if x < 0:
            x = 10

        self.dialog.geometry(f"{window_width}x{window_height}+{x}+{y}")

        try:
            icon_path = os.path.join(get_resource_dir(), "icon.ico")
            if os.path.exists(icon_path):
                self.dialog.iconbitmap(icon_path)
        except:
            pass

        self.create_widgets()
        self.dialog.focus_set()

        self.setup_hotkeys(self.dialog)

    def create_widgets(self):
        """Создает интерфейс настроек с прокруткой"""

        canvas = tk.Canvas(self.dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        main_frame = ttk.Frame(canvas, padding="20")
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)

        title_label = ttk.Label(
            main_frame,
            text="⚙️ Настройки",
            font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(0, 10))

        desc_label = ttk.Label(
            main_frame,
            text="Заполните данные для доступа вручную.\n"
                 "Введите Voice ID, x-zid и heygen_session и сохраните настройки.",
            font=('Arial', 9),
            foreground='gray'
        )
        desc_label.pack(pady=(0, 20))

        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True)

        # Voice ID
        ttk.Label(fields_frame, text="Voice ID:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.voice_id_entry = ttk.Entry(fields_frame, width=60, font=('Courier', 9))
        self.voice_id_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.voice_id_entry.insert(0, self.config_data.get('voice_id', ''))

        ttk.Label(fields_frame, text="Пример: 99633efc7a7945a4bb23011324740efb",
                  font=('Arial', 8), foreground='gray').grid(
            row=2, column=0, sticky=tk.W, pady=(0, 10)
        )

        # x-zid
        ttk.Label(fields_frame, text="x-zid:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.x_zid_entry = ttk.Entry(fields_frame, width=60, font=('Courier', 9))
        self.x_zid_entry.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.x_zid_entry.insert(0, self.config_data.get('x_zid', ''))

        # heygen_session
        ttk.Label(fields_frame, text="heygen_session:", font=('Arial', 10, 'bold')).grid(
            row=6, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.session_entry = ttk.Entry(fields_frame, width=60, font=('Courier', 9), show="●")
        self.session_entry.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.session_entry.insert(0, self.config_data.get('heygen_session', ''))

        self.show_session = tk.BooleanVar(value=False)

        def toggle_session_show():
            if self.show_session.get():
                self.session_entry.config(show="")
            else:
                self.session_entry.config(show="●")

        show_check = ttk.Checkbutton(
            fields_frame,
            text="Показать heygen_session",
            variable=self.show_session,
            command=toggle_session_show
        )
        show_check.grid(row=8, column=0, sticky=tk.W, pady=(0, 10))

        # Voice Engine
        ttk.Label(fields_frame, text="Voice Engine:", font=('Arial', 10, 'bold')).grid(
            row=10, column=0, sticky=tk.W, pady=(15, 5)
        )
        self.engine_var = tk.StringVar(value=self.config_data.get('voice_engine', 'elevenLabsV3'))
        engine_combo = ttk.Combobox(fields_frame, textvariable=self.engine_var,
                                    values=['elevenLabsV3', 'fish', 'elevenLabsV2'],
                                    state="readonly", width=30)
        engine_combo.grid(row=11, column=0, sticky=tk.W, pady=(0, 15))

        ttk.Label(fields_frame, text="elevenLabsV3 — стандартный | fish — другой движок",
                  font=('Arial', 8), foreground='gray').grid(
            row=12, column=0, sticky=tk.W, pady=(0, 5)
        )

        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        save_btn = ttk.Button(
            buttons_frame,
            text="💾 СОХРАНИТЬ",
            command=self.save_settings,
            width=20
        )
        save_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = ttk.Button(
            buttons_frame,
            text="❌ ОТМЕНА",
            command=self.dialog.destroy,
            width=20
        )
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        self.status_label = ttk.Label(
            main_frame,
            text="",
            foreground="gray",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        self.status_label.pack(fill=tk.X, pady=(10, 0))

        fields_frame.columnconfigure(0, weight=1)

    def save_settings(self):
        """Сохраняет настройки"""
        voice_id = self.voice_id_entry.get().strip()
        x_zid = self.x_zid_entry.get().strip()
        heygen_session = self.session_entry.get().strip()

        if not voice_id:
            self.status_label.config(text="❌ Voice ID не может быть пустым", foreground="red")
            return

        if not x_zid:
            self.status_label.config(text="❌ x-zid не может быть пустым", foreground="red")
            return

        if not heygen_session:
            self.status_label.config(text="❌ heygen_session не может быть пустым", foreground="red")
            return

        config_data = {
            "voice_id": voice_id,
            "x_zid": x_zid,
            "heygen_session": heygen_session,
            "voice_engine": self.engine_var.get()
        }

        try:
            current_dir = get_app_dir()
            config_path = os.path.join(current_dir, "config.json")

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.status_label.config(text="✅ Настройки сохранены!", foreground="green")
            self.result = config_data

            # Обновляем конфиг в главном окне (не трогаем комбобокс!)
            self.app.config = config_data.copy()
            self.app.api_status_label.config(
                text=f"✓ Конфиг настроен. Voice ID: {voice_id[:20]}...",
                foreground="green"
            )

            self.dialog.after(1000, self.dialog.destroy)

        except Exception as e:
            self.status_label.config(text=f"❌ Ошибка сохранения: {e}", foreground="red")


class VoiceSelectorDialog(HotkeyMixin):
    """Диалог выбора голоса с фильтрами"""

    # Словари для преобразования кодов в читаемые названия
    LANGUAGE_NAMES = {
        "ru": "Russian",
        "en": "English",
        "de": "German",
        "fr": "French",
        "es": "Espanol",
        "it": "Italian",
        "pt": "Portuguese",
        "ja": "Japanese",
        "ko": "Korean",
    }

    GENDER_NAMES = {
        "male": "Мужской",
        "female": "Женский",
        "neutral": "Нейтральный"
    }

    AGE_NAMES = {
        "young": "Молодой",
        "adult": "Взрослый",
        "senior": "Пожилой"
    }

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.result = None
        self.scroll_timer = None

        # Создаем окно
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Выбор голоса")
        self.dialog.geometry("900x650")
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 500)

        # Центрируем окно
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.center_window()

        # Загружаем данные
        self.all_voices = app.all_voices if hasattr(app, 'all_voices') else []
        self.favorites = app.favorites if hasattr(app, 'favorites') else []

        # ========== ДОБАВЛЯЕМ custom_voice ==========
        self.custom_voice = app.custom_voice if hasattr(app, 'custom_voice') else {
            'name': '🎤 Свой голос (из config.json)'}
        # ==========================================

        # Текущий режим: "all" или "favorites"
        self.current_mode = "all"

        # Настройка стилей для выделения
        style = ttk.Style()

        # Стиль для выделенной строки
        style.configure("Selected.TFrame", background="#e3f2fd")
        style.configure("Selected.TLabel", background="#e3f2fd", foreground="#1976d2")

        # Стиль для наведения
        style.configure("Hover.TFrame", background="#f5f5f5")
        style.configure("Hover.TLabel", background="#f5f5f5")

        # Значения фильтров
        self.language_var = tk.StringVar(value="Все")
        self.gender_var = tk.StringVar(value="Все")
        self.age_var = tk.StringVar(value="Все")

        # Создаем интерфейс
        self.create_widgets()

        # Обновляем списки фильтров и голосов
        self.update_filter_options()
        self.refresh_voice_list()

        self.dialog.focus_set()
        self.setup_hotkeys(self.dialog)

    def center_window(self):
        """Центрирует окно"""
        self.dialog.update_idletasks()
        width = 900
        height = 650
        x = (self.dialog.winfo_screenwidth() - width) // 2
        y = (self.dialog.winfo_screenheight() - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        """Создает интерфейс окна"""
        # Основной контейнер
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Разделяем на левую и правую панель
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ========== ЛЕВАЯ ПАНЕЛЬ ==========
        left_frame = ttk.Frame(paned, width=180)
        paned.add(left_frame, weight=0)

        ttk.Label(left_frame, text="Категории", font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        self.all_btn = ttk.Button(left_frame, text="📁 Все голоса",
                                  command=lambda: self.set_mode("all"))
        self.all_btn.pack(fill=tk.X, pady=2)

        self.fav_btn = ttk.Button(left_frame, text="⭐ Избранное",
                                  command=lambda: self.set_mode("favorites"))
        self.fav_btn.pack(fill=tk.X, pady=2)

        # ========== ПРАВАЯ ПАНЕЛЬ ==========
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # Верхняя панель с поиском и фильтрами
        top_frame = ttk.Frame(right_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # Поле поиска
        search_frame = ttk.Frame(top_frame)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.refresh_voice_list())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Фильтры (в отдельном фрейме)
        filters_frame = ttk.Frame(right_frame)
        filters_frame.pack(fill=tk.X, pady=(0, 10))

        # Язык
        ttk.Label(filters_frame, text="Язык:").pack(side=tk.LEFT, padx=(0, 5))

        # Комбобокс с возможностью ввода текста (для поиска)
        self.language_combo = ttk.Combobox(filters_frame, textvariable=self.language_var,
                                           width=15, state="normal")
        self.language_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.language_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_voice_list())
        self.language_combo.bind('<KeyRelease>', self.on_language_search)

        # Пол
        ttk.Label(filters_frame, text="Пол:").pack(side=tk.LEFT, padx=(0, 5))
        self.gender_combo = ttk.Combobox(filters_frame, textvariable=self.gender_var,
                                         width=10, state="readonly")
        self.gender_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.gender_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_voice_list())

        # Возраст
        ttk.Label(filters_frame, text="Возраст:").pack(side=tk.LEFT, padx=(0, 5))
        self.age_combo = ttk.Combobox(filters_frame, textvariable=self.age_var,
                                      width=10, state="readonly")
        self.age_combo.pack(side=tk.LEFT)
        self.age_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_voice_list())

        # Список голосов (с прокруткой)
        list_frame = ttk.Frame(right_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # ========== ДОБАВЛЯЕМ ФОН ДЛЯ СПИСКА ==========
        # Создаем фрейм с фоном
        list_container = ttk.Frame(list_frame, relief=tk.SUNKEN, borderwidth=1)
        list_container.pack(fill=tk.BOTH, expand=True)

        # Создаем Canvas + Scrollbar для прокрутки
        canvas = tk.Canvas(list_container, highlightthickness=0, bg='#f8f9fa')
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Фрейм внутри canvas
        self.voices_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=self.voices_frame, anchor="nw")

        # Прокрутка колесиком мыши
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # Привязываем прокрутку к canvas
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        def configure_scroll_region(event):
            # Задержка, чтобы избежать лишних вызовов
            self.dialog.after(10, self.update_scroll_region)

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
            # Обновляем прокрутку после изменения ширины
            self.dialog.after(10, self.update_scroll_region)

        self.voices_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)

        # Кнопка выбора (внизу правой панели)
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        self.select_btn = ttk.Button(buttons_frame, text="✅ Выбрать",
                                     command=self.select_voice, width=15)
        self.select_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Button(buttons_frame, text="❌ Отмена",
                   command=self.dialog.destroy, width=15).pack(side=tk.RIGHT, padx=5)

        # Сохраняем canvas для обновления прокрутки
        self.canvas = canvas
        self.canvas_window = canvas_window

    def add_voice_row(self, index, voice):
        """Добавляет строку с голосом"""
        row_frame = ttk.Frame(self.voices_frame)
        row_frame.pack(fill=tk.X, pady=1, padx=2)

        # Сохраняем voice_id во фрейме
        row_frame.voice_id = voice['id']

        # Переменная для отслеживания выделения
        row_frame.is_selected = False

        # ========== ЗВЕЗДОЧКА ТОЛЬКО ДЛЯ НЕ-CUSTOM ==========
        if voice['id'] != 'custom':
            is_fav = voice['id'] in self.favorites
            fav_btn = ttk.Button(row_frame, text="★" if is_fav else "☆",
                                 width=3, command=lambda: self.toggle_favorite(voice['id']))
            fav_btn.pack(side=tk.LEFT, padx=5)
        else:
            # Пустое место для custom
            empty_label = ttk.Label(row_frame, text="  ", width=3)
            empty_label.pack(side=tk.LEFT, padx=5)
        # =================================================

        # Название голоса
        display_name = voice.get('display', voice['name'])
        voice_label = ttk.Label(row_frame, text=display_name, cursor="hand2")
        voice_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Функции для выделения
        def on_enter(event):
            if not row_frame.is_selected:
                row_frame.config(style="Hover.TFrame")
                voice_label.config(style="Hover.TLabel")

        def on_leave(event):
            if not row_frame.is_selected:
                row_frame.config(style="TFrame")
                voice_label.config(style="TLabel")

        def on_click(event):
            # Снимаем выделение со всех строк
            for child in self.voices_frame.winfo_children():
                if hasattr(child, 'is_selected'):
                    child.is_selected = False
                    child.config(style="TFrame")
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ttk.Label):
                            subchild.config(style="TLabel")

            # Выделяем текущую строку
            row_frame.is_selected = True
            row_frame.config(style="Selected.TFrame")
            voice_label.config(style="Selected.TLabel")

        # Привязываем события
        row_frame.bind("<Enter>", on_enter)
        row_frame.bind("<Leave>", on_leave)
        row_frame.bind("<Button-1>", on_click)
        voice_label.bind("<Button-1>", on_click)

        # Двойной клик для выбора
        voice_label.bind("<Double-Button-1>", lambda e: self.select_voice_by_id(voice['id']))

        # Сохраняем ссылки
        row_frame.voice_label = voice_label

    def on_language_search(self, event):
        """Обработчик поиска по языку"""
        search_text = self.language_var.get().lower()

        if not search_text:
            # Если пусто, показываем все языки
            self.language_combo['values'] = self.all_languages
            return

        # Фильтруем языки по введенному тексту (но сохраняем оригинальный список)
        filtered = [lang for lang in self.all_languages if search_text in lang.lower()]
        self.language_combo['values'] = filtered

        # Если нажат Enter, применяем фильтр голосов
        if event.keysym == 'Return':
            self.refresh_voice_list()

        # Важно: не сбрасываем self.all_languages!

    def set_mode(self, mode):
        """Переключает режим: all или favorites"""
        self.current_mode = mode
        self.update_filter_options()  # Обновляем списки фильтров
        self.refresh_voice_list()

    def update_filter_options(self):
        """Обновляет списки фильтров на основе текущих голосов"""
        languages = set()
        genders = set()
        ages = set()

        voices_to_check = [v for v in self.all_voices if v['id'] != 'custom']  # исключаем custom

        if self.current_mode == "favorites":
            voices_to_check = [v for v in voices_to_check if v['id'] in self.favorites]

        for voice in voices_to_check:
            lang_code = voice.get('language', 'unknown')
            if lang_code in self.LANGUAGE_NAMES:
                languages.add(self.LANGUAGE_NAMES[lang_code])
            elif lang_code != 'unknown':
                languages.add(lang_code.capitalize())

            gender_code = voice.get('gender', 'unknown')
            if gender_code in self.GENDER_NAMES:
                genders.add(self.GENDER_NAMES[gender_code])
            elif gender_code != 'unknown':
                genders.add(gender_code.capitalize())

            age_code = voice.get('age', 'unknown')
            if age_code in self.AGE_NAMES:
                ages.add(self.AGE_NAMES[age_code])
            elif age_code != 'unknown':
                ages.add(age_code.capitalize())

        # Сохраняем полные списки
        self.all_languages = ["Все"] + sorted([l for l in languages if l != 'unknown'])
        self.all_genders = ["Все"] + sorted([g for g in genders if g != 'unknown'])
        self.all_ages = ["Все"] + sorted([a for a in ages if a != 'unknown'])

        # Обновляем комбобоксы
        self.language_combo['values'] = self.all_languages
        self.gender_combo['values'] = self.all_genders
        self.age_combo['values'] = self.all_ages

        # Сбрасываем фильтры, если текущее значение не в списке
        if self.language_var.get() not in self.all_languages:
            self.language_var.set("Все")
        if self.gender_var.get() not in self.all_genders:
            self.gender_var.set("Все")
        if self.age_var.get() not in self.all_ages:
            self.age_var.set("Все")

    def filter_voice(self, voice):
        """Проверяет, подходит ли голос под текущие фильтры"""
        # Для custom всегда показываем
        if voice['id'] == 'custom':
            return True

        # Проверка режима (избранное)
        if self.current_mode == "favorites" and voice['id'] not in self.favorites:
            return False

        # Проверка поиска
        search_text = self.search_var.get().lower()
        if search_text:
            display_name = voice.get('display', voice['name']).lower()
            if search_text not in display_name:
                return False

        # Проверка языка (с преобразованием в красивое название)
        language_filter = self.language_var.get()
        if language_filter != "Все":
            lang_code = voice.get('language', '')
            lang_display = self.LANGUAGE_NAMES.get(lang_code, lang_code.capitalize())
            if lang_display != language_filter:
                return False

        # Проверка пола
        gender_filter = self.gender_var.get()
        if gender_filter != "Все":
            gender_code = voice.get('gender', '')
            gender_display = self.GENDER_NAMES.get(gender_code, gender_code.capitalize())
            if gender_display != gender_filter:
                return False

        # Проверка возраста
        age_filter = self.age_var.get()
        if age_filter != "Все":
            age_code = voice.get('age', '')
            age_display = self.AGE_NAMES.get(age_code, age_code.capitalize())
            if age_display != age_filter:
                return False

        return True

    def refresh_voice_list(self):
        """Обновляет список голосов"""
        # Очищаем фрейм
        for widget in self.voices_frame.winfo_children():
            widget.destroy()

        # Фильтруем голоса (custom проходит фильтры)
        filtered_voices = [v for v in self.all_voices if self.filter_voice(v)]

        # Добавляем голоса в список
        for i, voice in enumerate(filtered_voices):
            self.add_voice_row(i, voice)

        # Обновляем прокрутку - НЕМНОГО ЗАДЕРЖКА, чтобы фрейм обновился
        self.dialog.after(50, self.update_scroll_region)

        # Если нет голосов
        if not filtered_voices:
            ttk.Label(self.voices_frame, text="Нет голосов", foreground="gray").pack(pady=20)
            self.dialog.after(50, self.update_scroll_region)

    def update_scroll_region(self):
        """Обновляет область прокрутки с задержкой"""
        if self.scroll_timer:
            self.dialog.after_cancel(self.scroll_timer)

        def do_update():
            self.canvas.update_idletasks()
            bbox = self.canvas.bbox("all")
            if bbox:
                # Убеждаемся, что область не меньше видимой
                canvas_height = self.canvas.winfo_height()
                if bbox[3] < canvas_height:
                    # Если содержимое меньше canvas, корректируем
                    bbox = (bbox[0], bbox[1], bbox[2], canvas_height)
                self.canvas.configure(scrollregion=bbox)
            else:
                self.canvas.configure(scrollregion=(0, 0, 0, 0))

        self.scroll_timer = self.dialog.after(50, do_update)

    def select_custom_voice(self):
        """Выбирает кастомный голос (из config.json)"""
        # Проверяем, есть ли voice_id в конфиге
        voice_id = self.app.config.get('voice_id') if self.app.config else None

        if voice_id:
            # Создаем виртуальный объект голоса
            self.result = {
                "id": voice_id,
                "name": "Свой голос",
                "display": "🎤 Свой голос (из config.json)"
            }
            self.dialog.destroy()
        else:
            messagebox.showwarning(
                "Внимание",
                "Сначала укажите Voice ID в настройках программы (⚙️ Настройки → Voice ID)"
            )

    def toggle_favorite(self, voice_id):
        """Переключает избранное"""
        if voice_id in self.favorites:
            self.favorites.remove(voice_id)
        else:
            self.favorites.append(voice_id)

        # Сохраняем в файл
        self.app.save_favorites(self.favorites)

        # Обновляем список
        self.refresh_voice_list()

    def select_voice(self):
        """Выбирает текущий выделенный голос"""
        # Ищем выделенный элемент
        for child in self.voices_frame.winfo_children():
            if hasattr(child, 'voice_id'):
                if child.voice_id == 'custom':
                    self.select_custom_voice()
                    return
                elif hasattr(child, 'voice_id') and child.focus_displayof():
                    self.select_voice_by_id(child.voice_id)
                    return

        # Если ничего не выделено, выбираем первый (кроме кастомного)
        for child in self.voices_frame.winfo_children():
            if hasattr(child, 'voice_id') and child.voice_id != 'custom':
                self.select_voice_by_id(child.voice_id)
                return

    def select_voice_by_id(self, voice_id):
        """Выбирает голос по ID"""
        if voice_id == 'custom':
            # Кастомный голос — берем из config
            voice_id_from_config = self.app.config.get('voice_id') if self.app.config else None
            if voice_id_from_config:
                self.result = {
                    "id": voice_id_from_config,
                    "name": "Свой голос",
                    "display": self.custom_voice.get('name', '🎤 Свой голос (из config.json)')
                }
                self.dialog.destroy()
            else:
                messagebox.showwarning(
                    "Внимание",
                    "Сначала укажите Voice ID в настройках программы (⚙️ Настройки → Voice ID)"
                )
            return

        for voice in self.all_voices:
            if voice['id'] == voice_id:
                self.result = voice
                self.dialog.destroy()
                return

class HeyGenApp(HotkeyMixin):
    def __init__(self, root):
        self.root = root
        self.root.title("HeyGen Voice Generator")
        self.root.geometry("900x700")

        icon_path = os.path.join(get_resource_dir(), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
                self.root.update_idletasks()
                self.root.iconify()
                self.root.deiconify()
            except Exception:
                pass

        # Переменные для интерфейса
        self.config = None
        self.voice_id_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готов к работе")
        self.progress_var = tk.DoubleVar()
        self.is_generating = False

        # Создаем менеджер лицензий
        self.license_manager = LicenseManager()

        # Проверяем лицензию
        if not self.license_manager.check_license():
            self.show_activation_dialog()
            if not self.license_manager.check_license():
                messagebox.showerror(
                    "Лицензия не активирована",
                    "Для работы программы необходима активация.\n"
                    "Программа будет закрыта."
                )
                self.root.destroy()
                return

        # Создаем интерфейс
        self.create_widgets()

        # Загружаем конфиг
        self.load_config()

        # Загружаем голоса (заполняем self.all_voices)
        self.load_all_voices()

        # Загружаем текст
        self.load_text_file()

        # Обновляем отображение текущего голоса
        self.update_current_voice_display()

        self.setup_hotkeys(self.root)

    def _set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def _set_progress(self, value):
        self.root.after(0, lambda: self.progress_var.set(value))

    def _show_info(self, title, text):
        self.root.after(0, lambda: messagebox.showinfo(title, text))

    def _show_error(self, title, text):
        self.root.after(0, lambda: messagebox.showerror(title, text))

    def load_voices(self):
        """Загружает список голосов из voices.json"""
        voices_path = os.path.join(get_resource_dir(), "voices.json")

        if not os.path.exists(voices_path):
            # Файл отсутствует — ошибка, без голосов программа не может работать
            messagebox.showerror(
                "Ошибка",
                "Файл voices.json не найден!\n\n"
                "Программа не может работать без списка голосов.\n"
                "Пожалуйста, переустановите приложение или свяжитесь с поддержкой."
            )
            sys.exit(1)  # Выходим из программы

        try:
            with open(voices_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            messagebox.showerror(
                "Ошибка",
                "Файл voices.json поврежден или имеет неверный формат.\n"
                "Пожалуйста, переустановите приложение."
            )
            sys.exit(1)
        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Не удалось загрузить voices.json: {e}"
            )
            sys.exit(1)

    def load_favorites(self):
        """Загружает список избранных голосов"""
        favorites_path = os.path.join(get_app_dir(), "favorites.json")

        if os.path.exists(favorites_path):
            try:
                with open(favorites_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('favorites', [])
            except:
                pass
        return []

    def save_favorites(self, favorites):
        """Сохраняет список избранных голосов"""
        favorites_path = os.path.join(get_app_dir(), "favorites.json")
        try:
            with open(favorites_path, 'w', encoding='utf-8') as f:
                json.dump({"favorites": favorites}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения избранного: {e}")

    def load_all_voices(self):
        """Загружает все голоса из voices.json (без комбобокса)"""
        voices_data = self.load_voices()
        if not voices_data:
            return

        self.all_voices = voices_data.get('voices', [])
        self.custom_voice = voices_data.get('custom_voice', {'name': '🎤 Свой голос (из config.json)'})
        self.favorites = self.load_favorites()

        # ========== ДОБАВЛЯЕМ CUSTOM_voice В ОБЩИЙ СПИСОК ==========
        # Создаем специальный голос для custom
        custom_voice_obj = {
            "id": "custom",
            "name": self.custom_voice.get('name', 'Свой голос'),
            "language": "custom",
            "gender": "custom",
            "age": "custom",
            "display": self.custom_voice.get('name', '🎤 Свой голос (из config.json)')
        }
        self.all_voices.append(custom_voice_obj)
        # ========================================================

    def show_activation_dialog(self):
        """Показывает диалог активации"""
        # Класс LicenseDialog уже определен в этом файле (в конце)
        dialog = LicenseDialog(self.root, self.license_manager)
        self.root.wait_window(dialog.dialog)

        # После закрытия диалога проверяем результат
        if not dialog.success:
            # Пользователь закрыл окно без активации
            pass

    def create_widgets(self):
        """Создает все элементы интерфейса"""
        # Главный контейнер
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Заголовок
        title_label = ttk.Label(main_frame, text="HeyGen Voice Generator",
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 10))

        # Панель настроек (добавляем кнопку настроек)
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки", padding="10")
        settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        settings_frame.columnconfigure(1, weight=1)

        # Голос
        ttk.Label(settings_frame, text="Голос:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        # Фрейм для выбора голоса
        voice_selector_frame = ttk.Frame(settings_frame)
        voice_selector_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
        voice_selector_frame.columnconfigure(0, weight=1)

        # Кнопка выбора голоса
        self.select_voice_btn = ttk.Button(voice_selector_frame, text="🎤 Выбрать голос",
                                           command=self.open_voice_selector, width=20)
        self.select_voice_btn.pack(side=tk.LEFT)

        # Метка с текущим голосом
        self.current_voice_label = ttk.Label(voice_selector_frame, text="Не выбран", foreground="gray")
        self.current_voice_label.pack(side=tk.LEFT, padx=(10, 0))

        # Кнопка настроек API (НОВАЯ)
        ttk.Button(settings_frame, text="⚙️ Настройки",
                   command=self.open_api_settings, width=15).grid(row=0, column=2, padx=(10, 0))

        # Статус API
        self.api_status_label = ttk.Label(settings_frame, text="", foreground="gray")
        self.api_status_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # Текстовая область
        text_frame = ttk.LabelFrame(main_frame, text="Текст для озвучки", padding="10")
        text_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15)
        self.text_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Кнопки управления текстом
        text_buttons_frame = ttk.Frame(text_frame)
        text_buttons_frame.grid(row=1, column=0, pady=(5, 0))

        ttk.Button(text_buttons_frame, text="Загрузить из text.txt",
                   command=self.load_text_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(text_buttons_frame, text="Сохранить в text.txt",
                   command=self.save_text_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(text_buttons_frame, text="Очистить",
                   command=lambda: self.text_area.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)

        # Информация о тексте
        self.text_info_label = ttk.Label(text_frame, text="Символов: 0")
        self.text_info_label.grid(row=2, column=0, pady=(5, 0))

        # Прогресс
        progress_frame = ttk.LabelFrame(main_frame, text="Прогресс", padding="10")
        progress_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            mode='determinate')
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Кнопки управления
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, pady=(0, 10))

        self.generate_btn = ttk.Button(buttons_frame, text="🎤 Сгенерировать",
                                       command=self.generate_audio, width=20)
        self.generate_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(buttons_frame, text="⏹️ Остановить",
                                   command=self.stop_generation, state=tk.DISABLED, width=20)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="ℹ️ О программе",
                   command=self.show_about, width=20).pack(side=tk.LEFT, padx=5)

        # Статус
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                      relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Настраиваем веса для расширения
        main_frame.rowconfigure(2, weight=1)

        # Привязываем событие изменения текста
        self.text_area.bind('<KeyRelease>', self.update_text_info)

    def open_voice_selector(self):
        """Открывает окно выбора голоса"""
        dialog = VoiceSelectorDialog(self.root, self)
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            voice = dialog.result

            if self.config is None:
                self.config = {}

            self.config['voice_id'] = voice['id']

            # Сохраняем в config.json
            config_path = os.path.join(get_app_dir(), "config.json")
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить config.json: {e}")
                return

            # Обновляем отображение
            display_name = voice.get('display', voice['name'])
            self.current_voice_label.config(text=display_name, foreground="green")
            self.voice_id_var.set(display_name)

            messagebox.showinfo("Успех", f"Выбран голос: {display_name}")

    def update_current_voice_display(self):
        """Обновляет отображение текущего выбранного голоса"""
        if self.config and self.config.get('voice_id'):
            voice_id = self.config['voice_id']
            for voice in self.all_voices:
                if voice['id'] == voice_id:
                    self.current_voice_label.config(text=voice.get('display', voice['name']), foreground="green")
                    return
        self.current_voice_label.config(text="Не выбран", foreground="gray")

    def load_config(self):
        """Загружает конфигурацию из config.json"""
        config_path = os.path.join(get_app_dir(), "config.json")

        if not os.path.exists(config_path):
            self.api_status_label.config(
                text="❌ config.json не найден! Нажмите '⚙️ Настройки' для создания",
                foreground="red"
            )
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

            required_fields = ["voice_id", "x_zid", "heygen_session"]
            missing = [f for f in required_fields if f not in self.config]

            if not missing:
                self.api_status_label.config(
                    text=f"✓ Конфиг настроен. Voice ID: {self.config['voice_id'][:20]}...",
                    foreground="green"
                )
            else:
                self.api_status_label.config(
                    text=f"⚠️ В config.json не хватает полей: {', '.join(missing)}",
                    foreground="orange"
                )
        except Exception as e:
            self.api_status_label.config(
                text=f"❌ Ошибка загрузки config.json: {e}",
                foreground="red"
            )

    def load_text_file(self):
        """Загружает текст из Текст/text.txt"""
        text_dir = get_text_dir()
        text_path = os.path.join(text_dir, "text.txt")

        if os.path.exists(text_path):
            try:
                with open(text_path, 'r', encoding='utf-8') as f:
                    self.text_area.delete(1.0, tk.END)
                    self.text_area.insert(1.0, f.read())
                self.update_text_info()
                self.status_var.set("Текст загружен из папки Текст")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл: {e}")

    def save_text_file(self):
        """Сохраняет текст в Текст/text.txt"""
        text = self.text_area.get(1.0, tk.END).strip()
        if text:
            try:
                text_dir = get_text_dir()
                text_path = os.path.join(text_dir, "text.txt")

                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_var.set("Текст сохранен в папку Текст")
                messagebox.showinfo("Успех", f"Текст сохранен в:\n{text_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")

    def update_text_info(self, event=None):
        """Обновляет информацию о тексте"""
        text = self.text_area.get(1.0, tk.END).strip()
        length = len(text)
        chunks = self.split_text_by_sentences(text, CHUNK_SIZE) if text else []
        self.text_info_label.config(
            text=f"Символов: {length} | Частей: {len(chunks)} (макс. {CHUNK_SIZE} символов на часть.)"
        )

    def split_text_by_sentences(self, text, max_size=5000):
        """Разбивает текст на части по предложениям"""
        if len(text) <= max_size:
            return [text]

        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(sentence) > max_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.append(sentence.strip())
                continue

            if len(current_chunk) + len(sentence) + 2 <= max_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def wrap_ssml(self, text, voice_id):
        """Оборачивает текст в SSML"""
        text = text.replace('"', '\\"').replace('«', '"').replace('»', '"')
        return f'<speak><voice name="{voice_id}"><prosody rate="1" pitch="0%">{text}</prosody></voice></speak>'

    def generate_audio_chunk(self, text_chunk, voice_id, x_zid, heygen_session, index, total):
        """Генерирует аудио для одной части"""
        self._set_status(f"Генерация части {index + 1}/{total}...")

        print(f"DEBUG: x_zid = {(x_zid[:20] + '...') if x_zid else 'None'}")
        print(f"DEBUG: heygen_session = {(heygen_session[:20] + '...') if heygen_session else 'None'}")
        print(f"DEBUG: voice_id = {voice_id}")

        cookie = f"x-movio-v-id={x_zid}; heygen_session={heygen_session}"

        # Получаем движок из конфига
        voice_engine = self.config.get('voice_engine', 'elevenLabsV3')

        payload = {
            "text_type": "ssml",
            "text": self.wrap_ssml(text_chunk, voice_id),
            "voice_id": voice_id,
            "preview": True,
            "settings": {"voice_engine_settings": {"engine_type": voice_engine, "stability": 0}},
            "language": "Russian",
            "voice_engine": voice_engine  # ← ИСПРАВЛЕНО: используем тот же движок
        }

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": "https://app.heygen.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "x-zid": x_zid,
            "cookie": cookie
        }

        try:
            response = requests.post(
                "https://api2.heygen.com/v2/online/text_to_speech.stream",
                headers=headers,
                json=payload,
                timeout=180
            )

            # Отладочный вывод
            print(f"Engine: {voice_engine}, Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Response: {response.text[:500]}")
                return None

            audio_data = b''
            for line in response.text.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('audio_bytes'):
                        audio_data += base64.b64decode(data['audio_bytes'])
                except:
                    continue

            return audio_data if audio_data else None

        except Exception as e:
            print(f"Error: {e}")
            return None

    def generate_audio(self):
        if self.is_generating:
            messagebox.showwarning("Внимание", "Генерация уже выполняется!")
            return

        if not self.config:
            messagebox.showerror("Ошибка", "Не загружен config.json")
            return

        # Получаем данные из конфига
        voice_id = self.config.get('voice_id')
        x_zid = self.config.get('x_zid')
        heygen_session = self.config.get('heygen_session')

        if not voice_id:
            messagebox.showerror("Ошибка", "Не выбран голос! Нажмите 'Выбрать голос'")
            return

        if not x_zid or not heygen_session:
            messagebox.showerror(
                "Ошибка",
                "Заполните x-zid и heygen_session в настройках"
            )
            return

        # Получаем текст
        text = self.text_area.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("Внимание", "Введите текст для озвучки")
            return

        # Разбиваем на части
        chunks = self.split_text_by_sentences(text, CHUNK_SIZE)

        # Спрашиваем подтверждение
        if not messagebox.askyesno("Подтверждение",
                                   f"Будет сгенерировано {len(chunks)} частей.\n"
                                   f"Общее время: ~{len(chunks) * DELAY} секунд.\n\n"
                                   f"Продолжить?"):
            return

        # Запускаем генерацию
        self.is_generating = True
        self.generate_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)

        thread = threading.Thread(target=self.generate_thread,
                                  args=(chunks, voice_id))
        thread.daemon = True
        thread.start()

    def generate_thread(self, chunks, voice_id):
        """Поток генерации аудио"""
        try:
            x_zid = self.config.get("x_zid")
            heygen_session = self.config.get("heygen_session")

            all_audio = b''
            success = 0

            for i, chunk in enumerate(chunks):
                if not self.is_generating:
                    self._set_status("Генерация остановлена пользователем")
                    break

                audio = self.generate_audio_chunk(chunk, voice_id, x_zid, heygen_session, i, len(chunks))
                if audio:
                    all_audio += audio
                    success += 1

                self._set_progress((i + 1) / len(chunks) * 100)

                if i < len(chunks) - 1:
                    time.sleep(DELAY)

            if all_audio and self.is_generating:
                # Сохраняем в папку Результаты
                results_dir = get_results_dir()
                voice_path = os.path.join(results_dir, "voice.mp3")

                with open(voice_path, "wb") as f:
                    f.write(all_audio)

                self._show_info(
                    "Успех",
                    f"Генерация завершена!\n\n"
                    f"Успешно: {success} из {len(chunks)} частей\n"
                    f"Файл: Результаты/voice.mp3"
                )
                self._set_status("Готово! Файл в папке Результаты")
            elif not self.is_generating:
                self._set_status("Генерация отменена")
            else:
                self._set_status("Ошибка: не удалось сгенерировать аудио")


        except Exception as e:
            self._show_error("Ошибка", str(e))
            self._set_status(f"Ошибка: {e}")
        finally:
            self.is_generating = False
            self.root.after(0, self.enable_buttons)

    def stop_generation(self):
        """Останавливает генерацию"""
        if self.is_generating:
            self.is_generating = False
            self.status_var.set("Остановка...")

    def enable_buttons(self):
        """Включает кнопки после генерации"""
        self.generate_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)

    def open_folder(self):
        """Открывает папку с программой"""
        folder = Path(__file__).parent

        if sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        elif os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def show_about(self):
        """Показывает информацию о программе"""
        license_info = self.license_manager.get_license_info()
        if license_info:
            expiry = license_info.get('expiry_date', 'Неизвестно')
            status = "Активна" if self.license_manager.is_license_valid(license_info) else "Истекла"
            license_text = f"\nЛицензия: {status}\nДействительна до: {expiry}"
        else:
            license_text = "\nЛицензия: Не активирована"

        messagebox.showinfo("О программе",
                            "HeyGen Cracked Voice Generator\nВерсия 2.0 (Desktop)\n\n"
                            "Генерация голоса\n"
                            f"{license_text}\n\n"
                            "© 2026 Copyright")

    def open_api_settings(self):
        """Открывает окно настроек API"""
        # Загружаем текущий конфиг если есть
        current_config = {}

        config_path = os.path.join(get_app_dir(), "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    current_config = json.load(f)
            except:
                pass

        # 🔥 ПЕРЕДАЕМ self (приложение), а не self.root
        dialog = ApiSettingsDialog(self, current_config)
        self.root.wait_window(dialog.dialog)

        # Если настройки были сохранены, перезагружаем конфиг
        if dialog.result:
            self.load_config()
            self.status_var.set("Настройки обновлены")


class LicenseDialog(HotkeyMixin):
    def __init__(self, parent, license_manager):
        self.license_manager = license_manager
        self.success = False

        # Создаем окно
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Активация HeyGen Voice Generator")
        self.dialog.geometry("650x600")
        self.dialog.resizable(True, True)  # ✅ ТЕПЕРЬ МОЖНО РАСТЯГИВАТЬ
        self.dialog.minsize(500, 500)

        # ✅ АВТОМАТИЧЕСКАЯ КОРРЕКТИРОВКА ПОЗИЦИИ
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        window_width = 650
        window_height = 600

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        if y + window_height > screen_height:
            y = max(0, screen_height - window_height - 30)
        if y < 0:
            y = 30
        if x + window_width > screen_width:
            x = max(0, screen_width - window_width - 10)
        if x < 0:
            x = 10

        self.dialog.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.machine_id = license_manager.get_machine_id()

        try:
            icon_path = os.path.join(get_resource_dir(), "icon.ico")
            if os.path.exists(icon_path):
                self.dialog.iconbitmap(icon_path)
        except:
            pass

        self.create_widgets_grid()
        self.dialog.focus_set()

        self.setup_hotkeys(self.dialog)

    def create_widgets_grid(self):
        """Создает интерфейс с прокруткой"""

        # ✅ ДОБАВЛЯЕМ ПРОКРУТКУ
        canvas = tk.Canvas(self.dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        main_frame = ttk.Frame(canvas, padding="20")
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)

        main_frame.columnconfigure(0, weight=1)

        row = 0

        title_label = ttk.Label(
            main_frame,
            text="🔐 Активация HeyGen Voice Generator",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=row, column=0, pady=(0, 15), sticky="ew")
        row += 1

        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        row += 1

        instruction_frame = ttk.LabelFrame(main_frame, text="📖 Инструкция по активации", padding="10")
        instruction_frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        instruction_frame.columnconfigure(0, weight=1)
        row += 1

        instruction_text = """1. Скопируйте код компьютера (находится ниже)
2. Отправьте его разработчику (email / telegram)
3. Получите лицензионный ключ
4. Вставьте ключ и нажмите "АКТИВИРОВАТЬ"

⚠️ ВНИМАНИЕ: Код привязан к этому компьютеру!"""

        instruction_label = ttk.Label(
            instruction_frame,
            text=instruction_text,
            justify=tk.LEFT,
            font=('Arial', 9)
        )
        instruction_label.grid(row=0, column=0, sticky="w")

        machine_frame = ttk.LabelFrame(main_frame, text="🖥️ Код этого компьютера", padding="10")
        machine_frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        machine_frame.columnconfigure(0, weight=1)
        row += 1

        display_id = self.machine_id[:50] + "..." if len(self.machine_id) > 50 else self.machine_id

        machine_id_label = ttk.Label(
            machine_frame,
            text=display_id,
            font=('Courier', 10, 'bold'),
            foreground='#0066CC',
            background='#F0F0F0',
            relief=tk.SUNKEN,
            padding=5
        )
        machine_id_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        def copy_machine_id():
            pyperclip.copy(self.machine_id)
            self.status_label.config(text="✅ Код скопирован!", foreground="green")
            self.dialog.after(2000, lambda: self.status_label.config(
                text="Введите лицензионный ключ", foreground="gray"
            ))

        copy_btn = ttk.Button(machine_frame, text="📋 Скопировать код", command=copy_machine_id)
        copy_btn.grid(row=1, column=0)

        key_frame = ttk.LabelFrame(main_frame, text="🎫 Лицензионный ключ", padding="10")
        key_frame.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        key_frame.columnconfigure(0, weight=1)
        row += 1

        self.key_entry = ttk.Entry(key_frame, width=70, font=('Courier', 10))
        self.key_entry.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        def paste_key():
            try:
                text = pyperclip.paste()
                if text:
                    self.key_entry.delete(0, tk.END)
                    self.key_entry.insert(0, text)
                    self.status_label.config(text="✅ Ключ вставлен", foreground="green")
                else:
                    self.status_label.config(text="⚠️ Буфер пуст", foreground="orange")
            except:
                self.status_label.config(text="❌ Ошибка вставки", foreground="red")

        paste_btn = ttk.Button(key_frame, text="📋 Вставить из буфера", command=paste_key)
        paste_btn.grid(row=1, column=0)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=row, column=0, pady=(10, 10))
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        row += 1

        self.activate_btn = ttk.Button(
            buttons_frame,
            text="✅ АКТИВИРОВАТЬ",
            command=self.activate,
            width=25
        )
        self.activate_btn.grid(row=0, column=0, padx=5, pady=5)

        exit_btn = ttk.Button(
            buttons_frame,
            text="❌ ВЫХОД",
            command=self.dialog.destroy,
            width=25
        )
        exit_btn.grid(row=0, column=1, padx=5, pady=5)

        self.status_label = ttk.Label(
            main_frame,
            text="Введите лицензионный ключ",
            foreground="gray",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        self.status_label.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        row += 1

        contact_frame = ttk.Frame(main_frame)
        contact_frame.grid(row=row, column=0, sticky="ew", pady=(15, 0))
        row += 1

        separator2 = ttk.Separator(contact_frame, orient='horizontal')
        separator2.pack(fill=tk.X, pady=(0, 10))

        contact_text = "📧 support@heygen-voice.com  |  💬 @heygen_support"
        contact_label = ttk.Label(
            contact_frame,
            text=contact_text,
            font=('Arial', 8),
            foreground='gray'
        )
        contact_label.pack()

        self.key_entry.focus()
        self.key_entry.bind('<Return>', lambda e: self.activate())

    def activate(self):
        """Активация лицензии"""
        license_key = self.key_entry.get().strip()

        if not license_key:
            self.status_label.config(text="❌ Введите лицензионный ключ!", foreground="red")
            self.key_entry.config(background="#FFE6E6")
            self.dialog.after(1000, lambda: self.key_entry.config(background="white"))
            return

        self.status_label.config(text="⏳ Проверка ключа...", foreground="orange")
        self.dialog.update()

        success, message = self.license_manager.verify_license_key(license_key)

        if success:
            self.status_label.config(text="✅ " + message, foreground="green")
            self.success = True
            messagebox.showinfo("Успех", f"Лицензия активирована!\n\n{message}")
            self.dialog.destroy()
        else:
            self.status_label.config(text="❌ " + message, foreground="red")
            self.key_entry.delete(0, tk.END)
            self.key_entry.focus()
            self.key_entry.config(background="#FFE6E6")
            self.dialog.after(1000, lambda: self.key_entry.config(background="white"))


def main():
    root = tk.Tk()
    app = HeyGenApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()