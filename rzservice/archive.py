import os
import shutil
import subprocess
import tempfile
import time
import zipfile

from . import crypto


class ArchiveError(Exception):
    pass


def _iter_entries(src_path):
    if os.path.isfile(src_path):
        yield os.path.basename(src_path), src_path, False
        return
    base = os.path.basename(os.path.normpath(src_path))
    for root, dirs, files in os.walk(src_path):
        dirs.sort()
        for name in sorted(dirs):
            full = os.path.join(root, name)
            yield os.path.join(base, os.path.relpath(full, src_path)), full, True
        for name in sorted(files):
            full = os.path.join(root, name)
            yield os.path.join(base, os.path.relpath(full, src_path)), full, False


def _total_filesize(entries):
    total = 0
    for _, full, is_dir in entries:
        if not is_dir:
            try:
                total += os.path.getsize(full)
            except OSError:
                pass
    return total


def _stats(src_path):
    if os.path.isfile(src_path):
        try:
            return 1, os.path.getsize(src_path)
        except OSError:
            return 1, 0
    files = 0
    total = 0
    for root, dirs, names in os.walk(src_path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
            files += 1
    return files, total


def _build_zip(zip_path, src_path, progress_cb=None, cancel_check=None):
    entries = list(_iter_entries(src_path))
    total_zip = _total_filesize(entries)
    done = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zf:
        for arc, full, is_dir in entries:
            if cancel_check is not None and cancel_check():
                raise crypto.CancelledError()
            if is_dir:
                zf.writestr(arc + "/", b"")
                continue
            with open(full, "rb") as fin, zf.open(arc, "w") as zi:
                while True:
                    if cancel_check is not None and cancel_check():
                        raise crypto.CancelledError()
                    buf = fin.read(1024 * 1024)
                    if not buf:
                        break
                    zi.write(buf)
                    done += len(buf)
                    if progress_cb is not None:
                        progress_cb("compress", done, max(total_zip, 1))
    if progress_cb is not None:
        progress_cb("compress", total_zip, max(total_zip, 1))


def find_rar():
    candidates = []
    env = os.environ
    for base in (env.get("ProgramFiles"), env.get("ProgramFiles(x86)"),
                 env.get("LocalAppData")):
        if base:
            candidates.append(os.path.join(base, "WinRAR", "Rar.exe"))
    reg = _registry_rar()
    if reg:
        candidates.insert(0, reg)
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    try:
        found = shutil.which("rar")
        if found:
            return found
    except Exception:
        pass
    return None


def _registry_rar():
    try:
        import winreg
    except ImportError:
        return None
    for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in (r"SOFTWARE\WinRAR", r"SOFTWARE\WOW6432Node\WinRAR"):
            try:
                with winreg.OpenKey(hkey, sub) as key:
                    for value_name in ("exe64", "exe32", "Path"):
                        try:
                            value = winreg.QueryValueEx(key, value_name)[0]
                        except OSError:
                            continue
                        if not value:
                            continue
                        value = value.strip('"')
                        if value.lower().endswith("rar.exe"):
                            return value
                        if value.lower().endswith("winrar.exe"):
                            cand = os.path.join(os.path.dirname(value), "Rar.exe")
                            if os.path.isfile(cand):
                                return cand
            except OSError:
                continue
    return None


def _run_rar(rar_exe, dst_path, src_path, cancel_check=None):
    args = [rar_exe, "a", "-ep1", "-idq", "-y", "-ma5", "-m5", "-r", dst_path, src_path]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, creationflags=flags)
    except OSError as exc:
        raise ArchiveError(f"Не удалось запустить WinRAR: {exc}") from exc
    while proc.poll() is None:
        if cancel_check is not None and cancel_check():
            proc.kill()
            proc.wait()
            raise crypto.CancelledError()
        time.sleep(0.1)
    out, err = proc.communicate()
    if proc.returncode != 0:
        detail = (err or out or "").strip()
        raise ArchiveError(f"WinRAR не смог создать архив: "
                          f"{detail or ('код ' + str(proc.returncode))}")


def archive(src_path, dst_path, password, fmt="zip", progress_cb=None,
            cancel_check=None,
            mem_kib=crypto.DEFAULT_MEM_KIB, time_cost=crypto.DEFAULT_TIME_COST,
            parallelism=crypto.DEFAULT_PARALLELISM):
    tmp_dir = tempfile.mkdtemp(prefix="rzservice_")
    try:
        if fmt == "rar":
            rar_exe = find_rar()
            if not rar_exe:
                raise ArchiveError("WinRAR не найден. Установите WinRAR или "
                                   "выберите формат ZIP.")
            tmp_archive = os.path.join(tmp_dir, "data.rar")
            if progress_cb is not None:
                progress_cb("rar", 0, 1)
            _run_rar(rar_exe, tmp_archive, src_path, cancel_check=cancel_check)
            if progress_cb is not None:
                progress_cb("rar", 1, 1)
        else:
            tmp_archive = os.path.join(tmp_dir, "data.zip")
            _build_zip(tmp_archive, src_path, progress_cb, cancel_check)
        files, total = _stats(src_path)
        crypto.encrypt_file(
            tmp_archive, dst_path, password,
            mem_kib=mem_kib, time_cost=time_cost, parallelism=parallelism,
            progress_cb=(lambda d, t: progress_cb("encrypt", d, t)
                         if progress_cb is not None else None),
            cancel_check=cancel_check,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return {"files": files, "size": total, "fmt": fmt}


def decrypt_to_temp(src_path, password, progress_cb=None, cancel_check=None):
    tmp_dir = tempfile.mkdtemp(prefix="rzunzip_")
    tmp_zip = os.path.join(tmp_dir, "data.archive")
    try:
        crypto.decrypt_file(src_path, tmp_zip, password,
                            progress_cb=progress_cb,
                            cancel_check=cancel_check)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return tmp_dir, tmp_zip


def open_archive(archive_path):
    try:
        return zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError):
        pass
    try:
        import rarfile
    except ImportError as exc:
        raise ArchiveError("Не удалось прочитать архив: RAR-модуль недоступен") from exc
    tool = find_rar()
    if tool:
        rarfile.UNRAR_TOOL = tool
    try:
        return rarfile.RarFile(archive_path)
    except rarfile.Error as exc:
        raise ArchiveError(f"Не удалось прочитать архив: {exc}") from exc


def delete_source(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
