import time


def format_size(num):
    num = float(num)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if num < 1024 or unit == "ТБ":
            if unit == "Б":
                return f"{int(num)} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} ТБ"


def format_date(t):
    try:
        stamp = time.mktime((t[0], t[1], t[2], t[3], t[4], t[5], 0, 0, -1))
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(stamp))
    except Exception:
        return "—"
