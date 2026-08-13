import re


def score(password):
    if not password:
        return 0.0
    length = len(password)
    classes = 0
    if re.search(r"[a-zа-я]", password):
        classes += 1
    if re.search(r"[A-ZА-Я]", password):
        classes += 1
    if re.search(r"\d", password):
        classes += 1
    if re.search(r"[^A-Za-zА-Яа-я0-9]", password):
        classes += 1
    length_score = min(1.0, length / 16)
    class_score = classes / 4
    result = 0.55 * length_score + 0.45 * class_score
    if re.fullmatch(r"(.)\1{3,}", password):
        result *= 0.4
    return min(1.0, round(result, 2))


def label(score):
    if score < 0.25:
        return "Слабый", "#e74c3c"
    if score < 0.5:
        return "Средний", "#f39c12"
    if score < 0.8:
        return "Надёжный", "#27ae60"
    return "Отличный", "#2ecc71"
