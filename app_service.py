import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from rzservice import archive, crypto, password_strength
from rzservice.uiutil import format_size

APP_NAME = "RZ Service"
ACCENT = "#2f6bb0"
ACCENT_HOVER = "#3a7fcf"
DANGER = "#a33a3a"
CARD_BG = "#1a2430"
DIVIDER = "#2c3c50"
SUBTITLE = "#7f9db9"
SECTION = "#9fd0ff"

FMT_LABELS = {"zip": "ZIP", "rar": "RAR"}


def count_dir(path):
    n = 0
    size = 0
    for root, dirs, files in os.walk(path):
        for name in files:
            try:
                size += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
            n += 1
    return n, size


class RZServiceApp:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME} — супер-защищённые архивы ZIP и RAR")
        self.root.minsize(820, 600)
        self.root.resizable(False, False)

        self.q = queue.Queue()
        self.worker = None
        self.busy = False
        self.cancel_flag = False

        self.rar_ok = bool(archive.find_rar())

        self.src_path = tk.StringVar()
        self.out_path = tk.StringVar()
        self.password = tk.StringVar()
        self.password2 = tk.StringVar()
        self.delete_src = tk.BooleanVar(value=False)
        self.fmt = "zip"

        self.src_info = tk.StringVar(value="Выберите папку или файл для шифрования")
        self.strength_text = tk.StringVar(value="Пароль не задан")
        self.status_text = tk.StringVar(value="Готов к работе")

        self._build_ui()
        self._center_window(880, 660)
        self.password.trace_add("write", self._on_password_change)
        self.root.after(100, self._poll_queue)

    def _center_window(self, w, h):
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _section(self, parent, text, row):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=SECTION).grid(row=row, column=0, columnspan=3,
                                              sticky="w", padx=22, pady=(14, 6))

    def _divider(self, parent, row):
        ctk.CTkFrame(parent, height=1, fg_color=DIVIDER).grid(
            row=row, column=0, columnspan=3, sticky="ew", padx=22, pady=2)

    def _build_ui(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(root, corner_radius=0, fg_color="#16202b", height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text=APP_NAME,
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color="#ffffff").grid(row=0, column=0,
                                                padx=(20, 6), pady=(10, 0), sticky="w")
        ctk.CTkLabel(header, text="Супер-защищённые архивы ZIP и RAR",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=SUBTITLE).grid(row=1, column=0,
                                               padx=(22, 6), pady=(0, 8), sticky="w")
        ctk.CTkButton(header, text="?", width=34, height=34, corner_radius=17,
                      fg_color="transparent", border_width=1,
                      command=self._about).grid(row=0, column=1, rowspan=2,
                                                padx=16, sticky="e")

        card = ctk.CTkFrame(root, corner_radius=16, fg_color=CARD_BG)
        card.grid(row=1, column=0, sticky="nsew", padx=16, pady=(14, 2))
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(0, minsize=140)

        self._section(card, "1 · ЧТО ЗАШИФРОВАТЬ", 0)
        self.path_box = ctk.CTkTextbox(card, height=62,
                                       font=ctk.CTkFont("Segoe UI", 12),
                                       wrap="word", state="disabled", corner_radius=10)
        self.path_box.grid(row=1, column=0, columnspan=3, sticky="ew",
                           padx=22, pady=2)
        self.path_box.configure(state="normal")
        self.path_box.insert("1.0", "Папка или файл не выбраны")
        self.path_box.configure(state="disabled")
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.grid(row=2, column=0, columnspan=3, sticky="ew", padx=22, pady=(8, 0))
        row2.grid_columnconfigure(2, weight=1)
        self.btn_folder = ctk.CTkButton(row2, text="Выбрать папку…", width=150,
                                        height=36, command=self._pick_folder)
        self.btn_folder.grid(row=0, column=0, padx=(0, 8))
        self.btn_file = ctk.CTkButton(row2, text="Выбрать файл…", width=140,
                                      height=36, command=self._pick_file)
        self.btn_file.grid(row=0, column=1, padx=(0, 8))
        ctk.CTkLabel(row2, textvariable=self.src_info, font=ctk.CTkFont("Segoe UI", 12),
                     text_color=SUBTITLE, justify="right").grid(row=0, column=2,
                                                                sticky="e")

        self._divider(card, 3)

        self._section(card, "2 · ПАРОЛЬ", 4)
        ctk.CTkLabel(card, text="Пароль", font=ctk.CTkFont("Segoe UI", 13)).grid(
            row=5, column=0, sticky="w", padx=22, pady=4)
        self.ent_pw = ctk.CTkEntry(card, textvariable=self.password, show="*")
        self.ent_pw.grid(row=5, column=1, sticky="ew", padx=(4, 8), pady=4)
        self.btn_show = ctk.CTkButton(card, text="Показать", width=90, height=34,
                                      command=self._toggle_show)
        self.btn_show.grid(row=5, column=2, sticky="w", padx=(0, 22), pady=4)
        ctk.CTkLabel(card, text="Повтор", font=ctk.CTkFont("Segoe UI", 13)).grid(
            row=6, column=0, sticky="w", padx=22, pady=4)
        self.ent_pw2 = ctk.CTkEntry(card, textvariable=self.password2, show="*")
        self.ent_pw2.grid(row=6, column=1, columnspan=2, sticky="ew",
                          padx=(4, 22), pady=4)
        self.strength_bar = ctk.CTkProgressBar(card, height=6,
                                               progress_color="#2ecc71")
        self.strength_bar.set(0)
        self.strength_bar.grid(row=7, column=0, columnspan=3, sticky="ew",
                               padx=22, pady=(10, 0))
        ctk.CTkLabel(card, textvariable=self.strength_text,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUBTITLE).grid(row=8, column=0, columnspan=3,
                                               sticky="w", padx=22, pady=(2, 0))

        self._divider(card, 9)

        self._section(card, "3 · ФОРМАТ И СОХРАНЕНИЕ", 10)
        ctk.CTkLabel(card, text="Формат", font=ctk.CTkFont("Segoe UI", 13)).grid(
            row=11, column=0, sticky="w", padx=22, pady=4)
        seg_values = ["ZIP", "RAR"] if self.rar_ok else ["ZIP"]
        self.seg_fmt = ctk.CTkSegmentedButton(card, values=seg_values,
                                              command=self._on_fmt,
                                              height=36)
        self.seg_fmt.set("ZIP")
        self.seg_fmt.grid(row=11, column=1, sticky="w", padx=(4, 8), pady=4)
        fmt_hint = ("Установите WinRAR для формата RAR" if not self.rar_ok
                    else "Внутри — ZIP/RAR, снаружи — AES-256-GCM")
        ctk.CTkLabel(card, text=fmt_hint, font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUBTITLE).grid(row=11, column=2, sticky="w",
                                               padx=(0, 22), pady=4)
        ctk.CTkLabel(card, text="Сохранить", font=ctk.CTkFont("Segoe UI", 13)).grid(
            row=12, column=0, sticky="w", padx=22, pady=4)
        self.ent_out = ctk.CTkEntry(card, textvariable=self.out_path,
                                    placeholder_text="Путь к защищённому файлу .rzx")
        self.ent_out.grid(row=12, column=1, sticky="ew", padx=(4, 8), pady=4)
        ctk.CTkButton(card, text="…", width=36, height=34,
                      command=self._pick_output).grid(row=12, column=2,
                                                      sticky="w", padx=(0, 22),
                                                      pady=4)
        self.chk_delete = ctk.CTkCheckBox(
            card, text="Удалить исходные данные после успешного шифрования",
            variable=self.delete_src, font=ctk.CTkFont("Segoe UI", 12))
        self.chk_delete.grid(row=13, column=0, columnspan=3, sticky="w",
                             padx=22, pady=(10, 18))

        footer = ctk.CTkFrame(root, corner_radius=0, fg_color="#141c25")
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, textvariable=self.status_text,
                                   font=ctk.CTkFont("Segoe UI", 12),
                                   text_color="#9fb6cd", anchor="w")
        self.status.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 4))
        self.btn_cancel = ctk.CTkButton(footer, text="Отмена", width=110, height=40,
                                        fg_color=DANGER, hover_color="#8a2f2f",
                                        command=self._cancel, state="disabled")
        self.btn_cancel.grid(row=0, column=1, padx=(0, 10), pady=8)
        self.btn_go = ctk.CTkButton(footer, text="", width=270, height=40,
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    font=ctk.CTkFont("Segoe UI", 14, "bold"),
                                    command=self._start)
        self.btn_go.grid(row=0, column=2, padx=(0, 18), pady=8)
        self.progress = ctk.CTkProgressBar(footer, height=5)
        self.progress.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.progress.set(0)
        self._update_go_text()

        self.ent_pw.bind("<Return>", lambda e: self._start())
        self.ent_pw2.bind("<Return>", lambda e: self._start())

    def _update_go_text(self):
        self.btn_go.configure(text=f"Создать защищённый {FMT_LABELS[self.fmt]}-архив")

    def _on_fmt(self, value):
        self.fmt = value.lower()
        self._update_go_text()

    def _pick_folder(self):
        path = filedialog.askdirectory(title="Выберите папку для шифрования")
        if path:
            self._set_path(path)

    def _pick_file(self):
        path = filedialog.askopenfilename(title="Выберите файл для шифрования")
        if path:
            self._set_path(path)

    def _pick_output(self):
        initial = self.out_path.get() or os.path.join(os.path.expanduser("~"), "archive.rzx")
        path = filedialog.asksaveasfilename(
            title="Куда сохранить защищённый архив",
            defaultextension=".rzx",
            initialfile=os.path.basename(initial) if initial else "archive.rzx",
            initialdir=os.path.dirname(initial) or os.path.expanduser("~"),
            filetypes=[("RZ Service контейнер", "*.rzx")])
        if path:
            self.out_path.set(path)

    def _set_path(self, path):
        self.src_path.set(path)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            self.src_info.set(f"Файл · {format_size(size)}")
            name = os.path.splitext(os.path.basename(path))[0]
        elif os.path.isdir(path):
            n, size = count_dir(path)
            self.src_info.set(f"Папка · файлов {n} · {format_size(size)}")
            name = os.path.basename(os.path.normpath(path))
        else:
            return
        self.path_box.configure(state="normal")
        self.path_box.delete("1.0", "end")
        self.path_box.insert("1.0", path)
        self.path_box.configure(state="disabled")
        if not self.out_path.get():
            base_dir = os.path.dirname(os.path.abspath(path))
            self.out_path.set(os.path.join(base_dir, name + ".rzx"))

    def _toggle_show(self):
        show = self.ent_pw.cget("show") == ""
        self.ent_pw.configure(show="" if not show else "*")
        self.ent_pw2.configure(show="" if not show else "*")
        self.btn_show.configure(text="Скрыть" if not show else "Показать")

    def _on_password_change(self, *args):
        pw = self.password.get()
        sc = password_strength.score(pw)
        lbl, color = password_strength.label(sc)
        self.strength_bar.set(sc)
        self.strength_bar.configure(progress_color=color)
        if not pw:
            self.strength_text.set("Пароль не задан")
        else:
            self.strength_text.set(f"Стойкость пароля: {lbl}")

    def _validate(self):
        src = self.src_path.get().strip()
        out = self.out_path.get().strip()
        pw = self.password.get()
        pw2 = self.password2.get()
        fmt = self.fmt
        if not src or not (os.path.isfile(src) or os.path.isdir(src)):
            messagebox.showerror(APP_NAME, "Выберите существующий файл или папку.")
            return None
        if fmt == "rar" and not self.rar_ok:
            messagebox.showerror(APP_NAME, "Для формата RAR требуется WinRAR. "
                                           "Установите WinRAR или выберите ZIP.")
            return None
        if not out:
            messagebox.showerror(APP_NAME, "Укажите путь для сохранения файла.")
            return None
        if not out.lower().endswith(".rzx"):
            out += ".rzx"
        if os.path.abspath(out) == os.path.abspath(src):
            messagebox.showerror(APP_NAME, "Путь сохранения совпадает с исходными данными.")
            return None
        if len(pw) < 4:
            messagebox.showerror(APP_NAME, "Пароль слишком короткий (минимум 4 символа).")
            return None
        if pw != pw2:
            messagebox.showerror(APP_NAME, "Пароли не совпадают.")
            return None
        if os.path.exists(out):
            if not messagebox.askyesno(APP_NAME,
                                       f"Файл уже существует:\n{out}\n\nПерезаписать?"):
                return None
        if self.delete_src.get():
            if not messagebox.askyesno(
                    APP_NAME,
                    "Исходные данные будут удалены после успешного шифрования.\n\n"
                    "Продолжить?"):
                self.delete_src.set(False)
        self.out_path.set(out)
        return src, out, pw, fmt

    def _start(self):
        if self.busy:
            return
        cfg = self._validate()
        if cfg is None:
            return
        src, out, pw, fmt = cfg
        self.cancel_flag = False
        self._set_busy(True)
        self.progress.set(0)
        self.status_text.set("Подготовка…")
        self.worker = threading.Thread(target=self._work, args=(src, out, pw, fmt),
                                       daemon=True)
        self.worker.start()

    def _work(self, src, out, pw, fmt):
        try:
            def progress(phase, done, total):
                if phase == "rar":
                    self.q.put(("progress", 40, "Создание RAR-архива…"))
                elif phase == "compress":
                    pct = int(done / max(total, 1) * 40)
                    self.q.put(("progress", pct, f"Сжатие в ZIP… {pct}%"))
                else:
                    pct = 40 + int(done / max(total, 1) * 60)
                    self.q.put(("progress", pct,
                                f"Супер-шифрование AES-256-GCM… {pct}%"))

            stats = archive.archive(src, out, pw, fmt=fmt,
                                    progress_cb=progress,
                                    cancel_check=self._is_cancelled)
            if not crypto.check_password(out, pw):
                raise crypto.WrongPasswordError("Проверка целостности не прошла")
            self.q.put(("progress", 100, "Проверка целостности пройдена"))
            if self.delete_src.get():
                archive.delete_source(src)
            self.q.put(("done", stats))
        except crypto.CancelledError:
            self._safe_remove(out)
            self.q.put(("cancelled",))
        except Exception as exc:
            self._safe_remove(out)
            self.q.put(("error", str(exc)))

    @staticmethod
    def _safe_remove(path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def _is_cancelled(self):
        return self.cancel_flag

    def _cancel(self):
        self.cancel_flag = True
        self.status_text.set("Отмена…")

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (self.btn_folder, self.btn_file, self.ent_out,
                       self.ent_pw, self.ent_pw2, self.chk_delete, self.seg_fmt):
            widget.configure(state=state)
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        self.btn_go.configure(state=state)

    def _poll_queue(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "progress":
            _, pct, text = msg
            self.progress.set(pct / 100)
            self.status_text.set(text)
        elif kind == "done":
            _, stats = msg
            self._set_busy(False)
            self.progress.set(1)
            lines = [f"Защищённый {FMT_LABELS.get(stats['fmt'], '')}-архив создан!",
                     f"Файлов: {stats['files']} · размер данных: {format_size(stats['size'])}",
                     f"\nФайл: {self.out_path.get()}",
                     "\nОткрыть его можно только в программе RZ unzip "
                     "по паролю."]
            if self.delete_src.get():
                lines.append("Исходные данные удалены.")
            self.status_text.set("Завершено")
            messagebox.showinfo(APP_NAME, "\n".join(lines))
        elif kind == "error":
            _, text = msg
            self._set_busy(False)
            self.status_text.set("Ошибка")
            messagebox.showerror(APP_NAME, text)
        elif kind == "cancelled":
            self._set_busy(False)
            self.progress.set(0)
            self.status_text.set("Операция отменена")

    def _about(self):
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} v1.1\n\n"
            "Создание супер-защищённых архивов ZIP и RAR.\n\n"
            "Как это работает:\n"
            "• данные сжимаются в ZIP или RAR;\n"
            "• весь архив шифруется AES-256-GCM;\n"
            "• пароль защищается Argon2id от подбора;\n"
            "• итог — файл .rzx, который не распознают "
            "Windows, WinRAR и 7-Zip;\n"
            "• имена файлов и структура полностью зашифрованы.\n\n"
            "Открыть .rzx можно только в программе RZ unzip "
            "после ввода пароля.")

    def run(self):
        self.root.mainloop()


def main():
    app = RZServiceApp()
    app.run()


if __name__ == "__main__":
    main()
