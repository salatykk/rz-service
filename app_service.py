import os
import queue
import string
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from rzservice import archive, crypto, password_strength
from rzservice.uiutil import format_size, resource_path

try:
    from PIL import Image
except ImportError:
    Image = None

APP_NAME = "RZ Service"
BG_WINDOW = "#2b2b2b"
BG_CARD = "#222222"
BG_TREE = "#1e1e1e"
TEXT = "#e6e6e6"
MUTED = "#9aa0a6"
FOLDER = "#f5a742"
FILE_C = "#c9c9c9"
ACCENT = "#3d7bd1"
ACCENT_HOVER = "#4f8ee6"
DANGER = "#b04a4a"
SECTION = "#8ab4f8"
DUMMY_SUFFIX = "__rz_dummy__"


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


def get_drives():
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:\\"
        if os.path.exists(path):
            drives.append(path)
    return drives


class RZServiceApp:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk(fg_color=BG_WINDOW)
        self.root.title(f"{APP_NAME} — супер-защищённые архивы ZIP и RAR")
        self.root.minsize(980, 640)

        self.q = queue.Queue()
        self.worker = None
        self.busy = False
        self.cancel_flag = False

        self.rar_ok = bool(archive.find_rar())

        self.src_path = tk.StringVar()
        self.password = tk.StringVar()
        self.password2 = tk.StringVar()
        self.delete_src = tk.BooleanVar(value=False)
        self.fmt = "zip"
        self.out_auto = ""

        self.src_info = tk.StringVar(value="")
        self.strength_text = tk.StringVar(value="Пароль не задан")
        self.status_text = tk.StringVar(value="Выберите папку в проводнике")
        self._stats_seq = 0

        self._build_ui()
        self._set_window_icon()
        self._center_window(1100, 700)
        self.password.trace_add("write", self._on_password_change)
        self.root.after(100, self._poll_queue)

    def _center_window(self, w, h):
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _set_window_icon(self):
        try:
            self.root.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

    def _load_icon(self, size):
        if Image is None:
            return None
        try:
            img = Image.open(resource_path("icon.png"))
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(size, size))
        except Exception:
            return None

    def _build_ui(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)

        main = ctk.CTkFrame(root, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, minsize=300)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self._build_left(main)
        self._build_right(main)

    def _build_left(self, main):
        left = ctk.CTkFrame(main, corner_radius=0, fg_color="transparent", width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 6), pady=16)
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(left, corner_radius=16, fg_color=BG_CARD)
        brand.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        brand.grid_columnconfigure(1, weight=1)
        icon = self._load_icon(52)
        if icon is not None:
            ctk.CTkLabel(brand, image=icon, text="").grid(
                row=0, column=0, rowspan=2, padx=(16, 4), pady=12, sticky="w")
            self._brand_icon = icon
        ctk.CTkLabel(brand, text=APP_NAME,
                     font=ctk.CTkFont("Segoe UI", 22, "bold"),
                     text_color=TEXT).grid(row=0, column=1, padx=(4, 16),
                                           pady=(14, 0), sticky="w")
        ctk.CTkLabel(brand, text="Супер-защищённые архивы\nZIP и RAR",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).grid(row=1, column=1, padx=(4, 16),
                                            pady=(0, 12), sticky="w")

        info = ctk.CTkFrame(left, corner_radius=16, fg_color=BG_CARD)
        info.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(info, text="Как это работает",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=SECTION).pack(anchor="w", padx=16, pady=(12, 4))
        for line in ("1. Выберите папку в проводнике",
                     "2. Укажите формат и пароль",
                     "3. Нажмите «Архивировать»",
                     "",
                     "Файл .rzx невозможно открыть без пароля — "
                     "ни Windows, ни WinRAR, ни 7-Zip."):
            ctk.CTkLabel(info, text=line, font=ctk.CTkFont("Segoe UI", 11),
                         text_color=MUTED, justify="left", anchor="w").pack(
                anchor="w", padx=16, pady=0)
        ctk.CTkLabel(info, text="", height=8).pack()

        footer = ctk.CTkFrame(left, corner_radius=0, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, textvariable=self.status_text,
                                   font=ctk.CTkFont("Segoe UI", 11),
                                   text_color=MUTED, anchor="w",
                                   justify="left", wraplength=280)
        self.status.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.progress = ctk.CTkProgressBar(footer, height=6)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.btn_cancel = ctk.CTkButton(footer, text="Отмена", height=36,
                                        fg_color=DANGER, hover_color="#8e3a3a",
                                        command=self._cancel, state="disabled")
        self.btn_cancel.grid(row=2, column=0, sticky="ew")

    def _build_right(self, main):
        right = ctk.CTkFrame(main, corner_radius=0, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        explorer = ctk.CTkFrame(right, corner_radius=16, fg_color=BG_TREE)
        explorer.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        explorer.grid_columnconfigure(0, weight=1)
        explorer.grid_rowconfigure(1, weight=1)

        exp_head = ctk.CTkFrame(explorer, fg_color="transparent")
        exp_head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        exp_head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(exp_head, text="Проводник",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(exp_head, text="выберите папку или файл",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).grid(row=0, column=1, sticky="w",
                                            padx=(10, 0), pady=(2, 0))

        holder = ctk.CTkFrame(explorer, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Explorer.Treeview",
                        background=BG_TREE,
                        fieldbackground=BG_TREE,
                        foreground=TEXT,
                        rowheight=26,
                        borderwidth=0,
                        indent=18,
                        font=("Segoe UI", 11))
        style.map("Explorer.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        self.tree = ttk.Treeview(holder, show="tree", selectmode="browse",
                                 style="Explorer.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("dir", foreground=FOLDER)
        self.tree.tag_configure("file", foreground=FILE_C)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._load_drives()

        arc = ctk.CTkFrame(right, corner_radius=16, fg_color=BG_CARD)
        arc.grid(row=1, column=0, sticky="ew")
        arc.grid_columnconfigure(1, weight=1)
        arc.grid_columnconfigure(0, minsize=130)

        ctk.CTkLabel(arc, text="Архивация",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w",
                                           padx=16, pady=(14, 4))
        ctk.CTkButton(arc, text="?", width=30, height=30, corner_radius=15,
                      fg_color="transparent", border_width=1,
                      command=self._about).grid(row=0, column=2, sticky="e",
                                                padx=(0, 16), pady=(10, 0))

        ctk.CTkLabel(arc, text="Папка:", font=ctk.CTkFont("Segoe UI", 12)).grid(
            row=1, column=0, sticky="w", padx=16, pady=4)
        self.path_label = ctk.CTkLabel(arc, text="Папка не выбрана",
                                       font=ctk.CTkFont("Segoe UI", 12),
                                       text_color=TEXT, anchor="w",
                                       justify="left", wraplength=400)
        self.path_label.grid(row=1, column=1, columnspan=2, sticky="ew",
                             padx=(4, 16), pady=4)
        ctk.CTkLabel(arc, textvariable=self.src_info,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).grid(row=2, column=1, columnspan=2,
                                            sticky="w", padx=(4, 16), pady=(0, 2))

        ctk.CTkLabel(arc, text="Формат:", font=ctk.CTkFont("Segoe UI", 12)).grid(
            row=3, column=0, sticky="w", padx=16, pady=4)
        fmt_values = ["ZIP", "RAR"] if self.rar_ok else ["ZIP"]
        self.menu_fmt = ctk.CTkOptionMenu(arc, values=fmt_values,
                                          command=self._on_fmt, height=34,
                                          width=130)
        self.menu_fmt.set("ZIP")
        self.menu_fmt.grid(row=3, column=1, sticky="w", padx=(4, 8), pady=4)
        ctk.CTkLabel(arc, text=("Установите WinRAR для формата RAR"
                                if not self.rar_ok
                                else "ZIP встроен · RAR через WinRAR"),
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).grid(row=3, column=2, sticky="w",
                                            padx=(0, 16), pady=4)

        ctk.CTkLabel(arc, text="Пароль:", font=ctk.CTkFont("Segoe UI", 12)).grid(
            row=4, column=0, sticky="w", padx=16, pady=4)
        self.ent_pw = ctk.CTkEntry(arc, textvariable=self.password, show="*")
        self.ent_pw.grid(row=4, column=1, sticky="ew", padx=(4, 8), pady=4)
        self.btn_show = ctk.CTkButton(arc, text="Показать", width=88, height=32,
                                      command=self._toggle_show)
        self.btn_show.grid(row=4, column=2, sticky="w", padx=(0, 16), pady=4)

        ctk.CTkLabel(arc, text="Повтор:", font=ctk.CTkFont("Segoe UI", 12)).grid(
            row=5, column=0, sticky="w", padx=16, pady=4)
        self.ent_pw2 = ctk.CTkEntry(arc, textvariable=self.password2, show="*")
        self.ent_pw2.grid(row=5, column=1, columnspan=2, sticky="ew",
                          padx=(4, 16), pady=4)

        self.strength_bar = ctk.CTkProgressBar(arc, height=5,
                                               progress_color="#2ecc71")
        self.strength_bar.set(0)
        self.strength_bar.grid(row=6, column=0, columnspan=3, sticky="ew",
                               padx=16, pady=(8, 0))
        ctk.CTkLabel(arc, textvariable=self.strength_text,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).grid(row=7, column=0, columnspan=3,
                                            sticky="w", padx=16, pady=(0, 2))

        self.chk_delete = ctk.CTkCheckBox(
            arc, text="Удалить исходные данные после архивации",
            variable=self.delete_src, font=ctk.CTkFont("Segoe UI", 11))
        self.chk_delete.grid(row=8, column=0, columnspan=3, sticky="w",
                             padx=16, pady=(6, 4))

        self.btn_go = ctk.CTkButton(arc, text="Архивировать", height=42,
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    font=ctk.CTkFont("Segoe UI", 15, "bold"),
                                    command=self._start)
        self.btn_go.grid(row=9, column=0, columnspan=3, sticky="ew",
                         padx=16, pady=(8, 16))

        self.ent_pw.bind("<Return>", lambda e: self._start())
        self.ent_pw2.bind("<Return>", lambda e: self._start())

    def _load_drives(self):
        for drive in get_drives():
            node = self.tree.insert("", "end", iid=drive, text=drive,
                                    tags=("dir",))
            self._add_dummy(node)

    @staticmethod
    def _dummy_of(path):
        return path + DUMMY_SUFFIX

    def _add_dummy(self, node):
        try:
            self.tree.insert(node, "end", iid=self._dummy_of(node), text="")
        except tk.TclError:
            pass

    def _maybe_expand(self, item):
        if not item or not self.tree.exists(item):
            return
        children = self.tree.get_children(item)
        if len(children) == 1 and children[0] == self._dummy_of(item):
            try:
                self.tree.delete(children[0])
            except tk.TclError:
                pass
            self._load_children(item)

    def _load_children(self, item):
        try:
            entries = sorted(os.scandir(item),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                child = self.tree.insert(item, "end", iid=entry.path,
                                         text=entry.name, tags=("dir",))
                self._add_dummy(child)
            else:
                self.tree.insert(item, "end", iid=entry.path,
                                 text=entry.name, tags=("file",))

    def _on_open(self, _event):
        item = self.tree.focus()
        if item:
            self._maybe_expand(item)
        for sel in self.tree.selection():
            self._maybe_expand(sel)

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        if not item or item.endswith(DUMMY_SUFFIX):
            return
        if os.path.isdir(item) or os.path.isfile(item):
            self._set_path(item)
        self._maybe_expand(item)

    def _set_path(self, path):
        self.src_path.set(path)
        if os.path.isfile(path):
            try:
                self.src_info.set(f"Файл · {format_size(os.path.getsize(path))}")
            except OSError:
                self.src_info.set("Файл")
        elif os.path.isdir(path):
            self.src_info.set("Подсчёт размера…")
            self._schedule_stats(path)
        else:
            return
        self.path_label.configure(text=path)
        self.out_auto = self._default_output(path)

    def _schedule_stats(self, path):
        self._stats_seq += 1
        seq = self._stats_seq
        threading.Thread(target=self._count_stats, args=(path, seq),
                         daemon=True).start()

    def _count_stats(self, path, seq):
        n, size = count_dir(path)
        self.q.put(("stats", seq, n, size))

    @staticmethod
    def _default_output(src):
        if os.path.isfile(src):
            name = os.path.splitext(os.path.basename(src))[0]
            folder = os.path.dirname(src)
        else:
            base = os.path.normpath(src)
            name = os.path.basename(base)
            folder = os.path.dirname(base)
        return os.path.join(folder, name + ".rzx")

    def _on_fmt(self, value):
        self.fmt = value.lower()

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
        if not src or not (os.path.isfile(src) or os.path.isdir(src)):
            messagebox.showerror(APP_NAME, "Выберите папку или файл в проводнике.")
            return None
        out = self.out_auto or self._default_output(src)
        fmt = self.fmt
        pw = self.password.get()
        pw2 = self.password2.get()
        if fmt == "rar" and not self.rar_ok:
            messagebox.showerror(APP_NAME, "Для формата RAR требуется WinRAR. "
                                           "Установите WinRAR или выберите ZIP.")
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
                    "Исходные данные будут удалены после архивации.\n\nПродолжить?"):
                self.delete_src.set(False)
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
        for widget in (self.ent_pw, self.ent_pw2, self.chk_delete,
                       self.menu_fmt, self.btn_go):
            widget.configure(state=state)
        self.tree.state(["disabled"] if busy else ["!disabled"])
        self.btn_cancel.configure(state="normal" if busy else "disabled")

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
            lines = ["Защищённый архив создан!",
                     f"Файлов: {stats['files']} · "
                     f"размер данных: {format_size(stats['size'])}",
                     f"\nФайл: {self.out_auto}",
                     "\nОткрыть его можно только в программе RZ unzip "
                     "по паролю."]
            if self.delete_src.get():
                lines.append("Исходные данные удалены.")
            self.status_text.set("Завершено")
            messagebox.showinfo(APP_NAME, "\n".join(lines))
        elif kind == "stats":
            _, seq, n, size = msg
            if seq == self._stats_seq:
                self.src_info.set(f"Папка · файлов {n} · {format_size(size)}")
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
            f"{APP_NAME} v1.2\n\n"
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
