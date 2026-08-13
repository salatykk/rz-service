import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from rzservice import archive, crypto
from rzservice.uiutil import format_date, format_size, resource_path

APP_NAME = "RZ unzip"
ACCENT = "#2f6bb0"
ACCENT_HOVER = "#3a7fcf"
DANGER = "#a33a3a"
SUBTITLE = "#7f9db9"


class PasswordDialog(ctk.CTkToplevel):
    def __init__(self, master, verify_fn):
        super().__init__(master)
        self.title("Пароль")
        self.resizable(False, False)
        self.verify_fn = verify_fn
        self.result = None
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="🔒",
                     font=ctk.CTkFont("Segoe UI", 26)).grid(row=0, column=0,
                                                            pady=(18, 0))
        ctk.CTkLabel(self, text="Контейнер защищён паролем",
                     font=ctk.CTkFont("Segoe UI", 15, "bold")).grid(
            row=1, column=0, pady=(4, 6), padx=24)
        self.entry = ctk.CTkEntry(self, show="*", font=ctk.CTkFont("Segoe UI", 13))
        self.entry.grid(row=2, column=0, sticky="ew", padx=24, pady=4)
        self.entry.focus_set()
        self.err = ctk.CTkLabel(self, text="", text_color="#e74c3c",
                                font=ctk.CTkFont("Segoe UI", 12))
        self.err.grid(row=3, column=0, pady=(2, 0))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=4, column=0, pady=(10, 18))
        ctk.CTkButton(row, text="Отмена", width=110, fg_color="transparent",
                      border_width=1, command=self._cancel).pack(side="left", padx=8)
        ctk.CTkButton(row, text="Открыть", width=130, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self._ok).pack(side="left",
                                                                       padx=8)
        self.entry.bind("<Return>", lambda e: self._ok())
        self.entry.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _ok(self):
        pw = self.entry.get()
        if self.verify_fn(pw):
            self.result = pw
            self.destroy()
        else:
            self.err.configure(text="Неверный пароль")

    def _cancel(self):
        self.result = None
        self.destroy()


class RZUnzipApp:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME} — просмотр и извлечение")
        self.root.minsize(840, 560)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.q = queue.Queue()
        self.busy = False
        self.cancel_flag = False

        self.rzx_path = None
        self.tmp_dir = None
        self.tmp_zip = None
        self.ar = None
        self.password = None

        self.status_text = tk.StringVar(value="Откройте файл .rzx")
        self.info_text = tk.StringVar(value="Файл не открыт")

        self._build_ui()
        self._set_window_icon()
        self._center_window(980, 640)
        self.root.after(100, self._poll_queue)

    def _set_window_icon(self):
        try:
            self.root.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

    def _center_window(self, w, h):
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

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
        ctk.CTkLabel(header, text="Открытие только по паролю",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=SUBTITLE).grid(row=1, column=0,
                                               padx=(22, 6), pady=(0, 8), sticky="w")
        ctk.CTkButton(header, text="?", width=34, height=34, corner_radius=17,
                      fg_color="transparent", border_width=1,
                      command=self._about).grid(row=0, column=1, rowspan=2,
                                                padx=16, sticky="e")

        toolbar = ctk.CTkFrame(root, corner_radius=0, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", padx=16, pady=(12, 4))
        toolbar.grid_columnconfigure(5, weight=1)
        self.btn_open = ctk.CTkButton(toolbar, text="Открыть .rzx", width=150,
                                      height=38, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER, command=self._open)
        self.btn_open.grid(row=0, column=0, padx=(0, 8))
        self.btn_extract_sel = ctk.CTkButton(toolbar, text="Извлечь выбранное",
                                             width=170, height=38,
                                             command=self._extract_selected)
        self.btn_extract_sel.grid(row=0, column=1, padx=(0, 8))
        self.btn_extract_all = ctk.CTkButton(toolbar, text="Извлечь всё",
                                             width=130, height=38,
                                             command=self._extract_all)
        self.btn_extract_all.grid(row=0, column=2, padx=(0, 8))
        self.btn_cancel = ctk.CTkButton(toolbar, text="Отмена", width=100, height=38,
                                        fg_color=DANGER, hover_color="#8a2f2f",
                                        command=self._cancel, state="disabled")
        self.btn_cancel.grid(row=0, column=6, sticky="e")

        tree_frame = ctk.CTkFrame(root, corner_radius=16)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(2, 8))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("RZ.Treeview",
                        background="#1a2430",
                        fieldbackground="#1a2430",
                        foreground="#dce4ee",
                        rowheight=28,
                        borderwidth=0,
                        font=("Segoe UI", 11))
        style.configure("RZ.Treeview.Heading",
                        background="#263545",
                        foreground="#9fd0ff",
                        borderwidth=0,
                        font=("Segoe UI", 11, "bold"))
        style.map("RZ.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])

        cols = ("name", "size", "compressed", "date")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 selectmode="extended", style="RZ.Treeview")
        self.tree.heading("name", text="Имя")
        self.tree.column("name", width=480, anchor="w")
        self.tree.heading("size", text="Размер")
        self.tree.column("size", width=110, anchor="e")
        self.tree.heading("compressed", text="Сжато")
        self.tree.column("compressed", width=110, anchor="e")
        self.tree.heading("date", text="Дата")
        self.tree.column("date", width=150, anchor="w")
        self.tree.tag_configure("dir", foreground="#6fb1ff")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(12, 4), pady=12)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", pady=12, padx=(0, 8))
        self.tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.tree.configure(xscrollcommand=hsb.set)

        footer = ctk.CTkFrame(root, corner_radius=0, fg_color="#141c25")
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.info_text,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color="#9fb6cd", anchor="w").grid(row=0, column=0,
                                                            sticky="ew",
                                                            padx=18, pady=(10, 0))
        ctk.CTkLabel(footer, textvariable=self.status_text,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUBTITLE, anchor="w").grid(row=1, column=0,
                                                           sticky="ew",
                                                           padx=18, pady=(0, 10))
        self.progress = ctk.CTkProgressBar(footer, height=5)
        self.progress.grid(row=2, column=0, sticky="ew")
        self.progress.set(0)

        self.tree.bind("<Double-1>", self._on_double_click)
        self._set_extract_buttons(False)

    def _set_extract_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        self.btn_extract_sel.configure(state=state)
        self.btn_extract_all.configure(state=state)

    def _open(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Открыть контейнер RZ Service",
            filetypes=[("RZ Service контейнер", "*.rzx"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            crypto.probe(path)
        except crypto.ContainerError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        dlg = PasswordDialog(self.root, lambda pw: self._verify(path, pw))
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        self._close()
        self.password = dlg.result
        self.rzx_path = path
        self._decrypt_and_load()

    def _verify(self, path, pw):
        try:
            return crypto.check_password(path, pw)
        except crypto.ContainerError:
            return False

    def _decrypt_and_load(self):
        self.cancel_flag = False
        self._set_busy(True)
        self.progress.set(0)
        self.status_text.set("Расшифровка контейнера…")
        thread = threading.Thread(target=self._work_open,
                                  args=(self.rzx_path, self.password), daemon=True)
        thread.start()

    def _work_open(self, path, pw):
        try:
            tmp_dir, tmp_zip = archive.decrypt_to_temp(
                path, pw,
                progress_cb=lambda d, t: self.q.put(
                    ("progress", int(d / max(t, 1) * 100))),
                cancel_check=self._is_cancelled)
            self.q.put(("loaded", tmp_dir, tmp_zip))
        except crypto.CancelledError:
            self.q.put(("cancelled",))
        except Exception as exc:
            self.q.put(("error", str(exc)))

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        infos = self.ar.infolist()
        infos.sort(key=lambda zi: (not zi.is_dir(), zi.filename.lower()))
        total_size = 0
        for zi in infos:
            name = zi.filename.rstrip("/")
            if zi.is_dir():
                self.tree.insert("", "end", iid=zi.filename,
                                 values=(name + "/", "—", "—",
                                         format_date(zi.date_time)),
                                 tags=("dir",))
            else:
                total_size += zi.file_size
                self.tree.insert("", "end", iid=zi.filename,
                                 values=(name, format_size(zi.file_size),
                                         format_size(zi.compress_size),
                                         format_date(zi.date_time)))
        self.info_text.set(f"Элементов: {len(infos)} · всего: {format_size(total_size)}")

    def _selected_members(self):
        selected = set(self.tree.selection())
        if not selected:
            return None
        members = []
        for zi in self.ar.infolist():
            if zi.filename in selected:
                members.append(zi)
            elif zi.filename.endswith("/") and zi.filename in selected:
                members.append(zi)
            elif any(zi.filename.startswith(prefix) for prefix in selected
                     if prefix.endswith("/")):
                members.append(zi)
        return members or None

    def _extract_selected(self):
        if self.ar is None or self.busy:
            return
        members = self._selected_members()
        if members is None:
            messagebox.showinfo(APP_NAME, "Выберите файлы или папки в списке.")
            return
        dest = filedialog.askdirectory(title="Куда извлечь выбранное")
        if not dest:
            return
        self._do_extract(members, dest)

    def _extract_all(self):
        if self.ar is None or self.busy:
            return
        dest = filedialog.askdirectory(title="Куда извлечь всё содержимое")
        if not dest:
            return
        self._do_extract(self.ar.infolist(), dest)

    def _do_extract(self, members, dest):
        self.cancel_flag = False
        self._set_busy(True)
        self.progress.set(0)
        self.status_text.set("Извлечение…")
        thread = threading.Thread(target=self._work_extract,
                                  args=(members, dest), daemon=True)
        thread.start()

    def _work_extract(self, members, dest):
        try:
            total = len(members)
            done = 0
            with archive.open_archive(self.tmp_zip) as ar:
                for zi in members:
                    if self._is_cancelled():
                        raise crypto.CancelledError()
                    ar.extract(zi, dest)
                    done += 1
                    self.q.put(("progress", int(done / max(total, 1) * 100)))
            self.q.put(("extract_done", dest, total))
        except crypto.CancelledError:
            self.q.put(("cancelled",))
        except Exception as exc:
            self.q.put(("error", str(exc)))

    def _on_double_click(self, _event):
        if self.ar is None:
            return
        messagebox.showinfo(APP_NAME,
                            "Для извлечения файлов используйте кнопки "
                            "'Извлечь выбранное' или 'Извлечь всё'.")

    def _close(self):
        if self.ar is not None:
            try:
                self.ar.close()
            except Exception:
                pass
            self.ar = None
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = None
            self.tmp_zip = None
        self.rzx_path = None
        self.password = None
        self.tree.delete(*self.tree.get_children())
        self.info_text.set("Файл не открыт")
        self.status_text.set("Файл закрыт")
        self.progress.set(0)
        self._set_extract_buttons(False)

    def _cancel(self):
        self.cancel_flag = True
        self.status_text.set("Отмена…")

    def _is_cancelled(self):
        return self.cancel_flag

    def _set_busy(self, busy):
        self.busy = busy
        self.btn_open.configure(state="disabled" if busy else "normal")
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        if busy:
            self._set_extract_buttons(False)

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
            _, pct = msg
            self.progress.set(pct / 100)
        elif kind == "loaded":
            _, tmp_dir, tmp_zip = msg
            self.tmp_dir, self.tmp_zip = tmp_dir, tmp_zip
            try:
                self.ar = archive.open_archive(self.tmp_zip)
            except archive.ArchiveError as exc:
                self._close()
                self._set_busy(False)
                self.status_text.set("Ошибка")
                messagebox.showerror(APP_NAME, str(exc))
                return
            self._populate()
            self._set_busy(False)
            self._set_extract_buttons(True)
            self.progress.set(1)
            self.status_text.set(f"Открыт: {self.rzx_path}")
        elif kind == "extract_done":
            _, dest, total = msg
            self._set_busy(False)
            self.progress.set(1)
            self.status_text.set("Извлечение завершено")
            messagebox.showinfo(APP_NAME,
                                f"Извлечено элементов: {total}\n\nВ папку:\n{dest}")
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
            "Программа для открытия супер-защищённых архивов "
            "RZ Service (.rzx).\n\n"
            "Без ввода правильного пароля содержимое не может быть "
            "показано или извлечено ни этой программой, ни Windows, "
            "ни WinRAR, ни любыми другими средствами.\n\n"
            "Защита: AES-256-GCM + Argon2id.\n"
            "Внутренние форматы: ZIP и RAR.")

    def _on_close(self):
        self._close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = RZUnzipApp()
    app.run()


if __name__ == "__main__":
    main()
