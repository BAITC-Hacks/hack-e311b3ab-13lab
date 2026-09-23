import re
from datetime import date, timedelta


MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "мая": 5, "июн": 6, "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12}
ORDINALS = {"первого": 1, "второго": 2, "третьего": 3, "четвертого": 4, "пятого": 5, "шестого": 6, "седьмого": 7, "восьмого": 8, "девятого": 9, "десятого": 10, "одиннадцатого": 11, "двенадцатого": 12, "тринадцатого": 13, "четырнадцатого": 14, "пятнадцатого": 15, "шестнадцатого": 16, "семнадцатого": 17, "восемнадцатого": 18, "девятнадцатого": 19, "двадцатого": 20, "тридцатого": 30}


def resolve_deadline(value: str | None, meeting_date: str):
    if not value:
        return None
    anchor = date.fromisoformat(meeting_date)
    phrase = value.casefold().replace("ё", "е")
    phrase = re.sub(r"(\w+)ому\b", r"\1ого", phrase)
    explicit = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", phrase)
    if explicit:
        try:
            return date.fromisoformat(explicit.group())
        except ValueError:
            return None
    numeric = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](20\d{2}))?\b", phrase)
    if numeric:
        try:
            return date(int(numeric[3] or anchor.year), int(numeric[2]), int(numeric[1]))
        except ValueError:
            return None
    month = next((number for prefix, number in MONTHS.items() if re.search(r"\b" + prefix, phrase)), None)
    if month:
        day_match = re.search(r"\b(\d{1,2})\b", phrase)
        day = int(day_match[1]) if day_match else next((number for word, number in ORDINALS.items() if word in phrase), None)
        if not day_match and day and day < 10:
            day += 20 if "двадцать " in phrase else 30 if "тридцать " in phrase else 0
        year_match = re.search(r"\b20\d{2}\b", phrase)
        if day:
            try:
                return date(int(year_match.group()) if year_match else anchor.year, month, day)
            except ValueError:
                return None
    if re.search(r"\b(сегодня|бүгін)\b", phrase):
        return anchor
    if re.search(r"\b(завтра|ертең)\b", phrase):
        return anchor + timedelta(days=1)
    if re.search(r"(?:через|за)\s+(?:две|2)\s+недел", phrase):
        return anchor + timedelta(days=14)
    if re.search(r"(?:через|за)\s+(?:одну\s+|1\s+)?неделю", phrase):
        return anchor + timedelta(days=7)
    duration = re.search(r"(?:через|за|максимум)\s+(\d+|десять|три|пять)\s+дн", phrase)
    if duration:
        numbers = {"десять": 10, "три": 3, "пять": 5}
        days = int(duration[1]) if duration[1].isdigit() else numbers[duration[1]]
        return anchor + timedelta(days=days) if days <= 366 else None
    kazakh_duration = re.search(r"\b(\d+|екі|бір)\s+(күн|апта)(?:нен|дан|ден|тан)?\s+кейін\b", phrase)
    if kazakh_duration:
        amount = int(kazakh_duration[1]) if kazakh_duration[1].isdigit() else {"екі": 2, "бір": 1}[kazakh_duration[1]]
        days = amount * (7 if kazakh_duration[2] == "апта" else 1)
        return anchor + timedelta(days=days) if days <= 366 else None
    weekdays = {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4, "суббот": 5, "воскресень": 6}
    for prefix, weekday in weekdays.items():
        if re.search(r"\b" + prefix, phrase):
            difference = (weekday - anchor.weekday()) % 7
            if difference:
                return anchor + timedelta(days=difference)
    return None


def ground_deadlines(analysis, meeting_date):
    for action in analysis.actions:
        if not action.deadline_text:
            event = re.search(r"\bпо итогам (?:этого )?совещания(?: с подрядчиками)?\b", action.evidence, re.IGNORECASE)
            if event:
                action.deadline_text = event.group()
        if action.deadline_resolution == "uncertain" or (action.deadline_text and re.search(r"(?:мне\s+)?больше недели", action.deadline_text, re.IGNORECASE)):
            action.deadline_resolution = "uncertain"
            action.due_date = None
            action.needs_review = True
            continue
        if action.deadline_resolution == "conflict":
            action.due_date = None
            analysis.warnings.append(f"Противоречивый срок — проверьте варианты и источники: {action.title}")
            continue
        if action.deadline_text and re.search(r"\b(?:после\s+(?:совещания|встречи|согласования|завершения|получения)|по\s+итогам\s+(?:этого\s+)?совещания)\b", action.deadline_text, re.IGNORECASE):
            action.deadline_resolution = "event"
            action.due_date = None
            continue
        action.due_date = resolve_deadline(action.deadline_text, meeting_date)
        action.deadline_resolution = "resolved" if action.due_date else "ambiguous" if action.deadline_text else "unspecified"
        if action.deadline_text and action.due_date is None:
            analysis.warnings.append(f"Уточните календарную дату: «{action.deadline_text}» — {action.title}")
    analysis.warnings = list(dict.fromkeys(analysis.warnings))
    return analysis
