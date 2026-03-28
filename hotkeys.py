"""
Модуль для универсальных горячих клавиш:
- выделить всё
- копировать
- вырезать
- вставить

Работает независимо от раскладки:
- Windows: Ctrl + физические A/C/V/X
- macOS:   Command + физические A/C/V/X

Важно:
Для macOS здесь использованы стандартные keycode обычной ANSI-клавиатуры Tk/Aqua.
Если у тебя на конкретном Mac окажутся другие keycode, их можно быстро
отладить через временный print(event.keycode).
"""

import tkinter as tk
from tkinter import scrolledtext

# Карта: windowing system -> physical keycode -> virtual event
#
# win32:
#   A=65, C=67, V=86, X=88
#
# aqua (типичные keycode для обычной Mac ANSI-клавиатуры):
#   A=0, X=7, C=8, V=9
WINDOW_SYSTEM_KEYMAPS = {
    "win32": {
        65: "<<SelectAll>>",
        67: "<<Copy>>",
        86: "<<Paste>>",
        88: "<<Cut>>",
    },
    "aqua": {
        0: "<<SelectAll>>",
        8: "<<Copy>>",
        9: "<<Paste>>",
        7: "<<Cut>>",
    },
}

ENTRY_LIKE_CLASSES = {
    "Entry",
    "TEntry",
    "Spinbox",
    "TSpinbox",
    "TCombobox",
}

TEXT_LIKE_CLASSES = {
    "Text",
}


class HotkeyMixin:
    """Миксин для горячих клавиш, независимых от раскладки."""

    def setup_hotkeys(self, window):
        """Настраивает горячие клавиши для конкретного окна (Toplevel / root)."""
        if getattr(window, "_layout_hotkeys_installed", False):
            return

        window._layout_hotkeys_installed = True

        window_system = window.tk.call("tk", "windowingsystem")
        keymap = WINDOW_SYSTEM_KEYMAPS.get(window_system)

        # Для неподдерживаемых систем просто ничего не ломаем.
        if not keymap:
            return

        # На macOS нужен Command, на Windows — Control.
        sequence = "<Command-KeyPress>" if window_system == "aqua" else "<Control-KeyPress>"

        def on_modified_keypress(event):
            widget = event.widget

            if not self._is_text_input_widget(widget):
                return None

            virtual_event = keymap.get(event.keycode)
            if not virtual_event:
                return None

            if virtual_event == "<<SelectAll>>":
                self.cmd_select_all(widget)
            elif virtual_event == "<<Copy>>":
                self.cmd_copy(widget)
            elif virtual_event == "<<Cut>>":
                self.cmd_cut(widget)
            elif virtual_event == "<<Paste>>":
                self.cmd_paste(widget)
            else:
                return None

            return "break"

        # Вешаем именно на окно, а не bind_all, чтобы не плодить дубли между диалогами.
        window.bind(sequence, on_modified_keypress, add="+")

    def _is_text_input_widget(self, widget):
        """Проверяет, что виджет — поле ввода текста."""
        try:
            widget_class = widget.winfo_class()
        except Exception:
            return False

        if widget_class in ENTRY_LIKE_CLASSES:
            return True

        if widget_class in TEXT_LIKE_CLASSES:
            return True

        if isinstance(widget, scrolledtext.ScrolledText):
            return True

        return False

    def cmd_copy(self, widget):
        try:
            widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def cmd_cut(self, widget):
        try:
            widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def cmd_paste(self, widget):
        try:
            widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    def cmd_select_all(self, widget):
        try:
            widget_class = widget.winfo_class()

            if widget_class in ENTRY_LIKE_CLASSES:
                widget.select_range(0, tk.END)
                widget.icursor(tk.END)
                return

            if widget_class in TEXT_LIKE_CLASSES or isinstance(widget, scrolledtext.ScrolledText):
                widget.tag_add(tk.SEL, "1.0", "end-1c")
                widget.mark_set(tk.INSERT, "end-1c")
                widget.see(tk.INSERT)
                return

        except tk.TclError:
            pass