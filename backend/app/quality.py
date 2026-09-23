import re

from app.models import DeadlineAlternative, NumericFragment


NUMBER_PATTERN = re.compile(
    r"\d|\b(?:ноль|один|одна|одно|два|две|три|четыре|пять|шесть|семь|восемь|девять|"
    r"десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|шестнадцать|"
    r"семнадцать|восемнадцать|девятнадцать|двадцать|тридцать|сорок|пятьдесят|"
    r"шестьдесят|семьдесят|восемьдесят|девяносто|сто|тысяч\w*|миллион\w*|полгода|"
    r"бір|екі|үш|төрт|бес|алты|жеті|сегіз|тоғыз|он|жиырма|отыз|қырық|елу|"
    r"алпыс|жетпіс|сексен|тоқсан|жүз|мың)\b", re.IGNORECASE,
)


def normalized(value):
    return " ".join(value.casefold().split())


def source_words(value):
    return " ".join(re.findall(r"\w+|%", value.casefold()))


def validate_summary_quotes(summary, segments):
    transcript = source_words(" ".join(segment.text for segment in segments))
    def checked(match):
        quote = source_words(match.group(1))
        return match.group() if quote and quote in transcript else "[Цитата не совпала с источником — требуется проверка]"
    return re.sub(r"«([^»]+)»", checked, summary)


def numeric_fragments(segments, summary):
    result = []
    seen = set()
    for segment in segments:
        for sentence in re.split(r"(?<=[.!?])\s+", segment.text):
            key = normalized(sentence)
            if NUMBER_PATTERN.search(sentence) and key not in seen:
                seen.add(key)
                result.append(NumericFragment(segment_id=segment.id, text=sentence, included=source_words(sentence) in source_words(summary)))
    return result


def validate_details(analysis, segments):
    transcript = normalized(" ".join(segment.text for segment in segments))
    sources = {segment.id: normalized(segment.text) for segment in segments}
    for action in analysis.actions:
        for field in ("issued_by", "deliverable", "condition"):
            evidence = getattr(action, field + "_evidence")
            if getattr(action, field) and (not evidence or not normalized(evidence) or normalized(evidence) not in transcript):
                analysis.warnings.append(f"Поле {field} требует подтверждения источником: {action.title}")
                setattr(action, field, None)
                setattr(action, field + "_evidence", None)
        valid = []
        seen = set()
        for alternative in action.deadline_alternatives:
            key = normalized(alternative.text)
            if key and key in sources.get(alternative.segment_id, "") and key not in seen:
                valid.append(alternative)
                seen.add(key)
            elif not key or key not in sources.get(alternative.segment_id, ""):
                analysis.warnings.append(f"Отклонён вариант срока без точного источника: {action.title}")
        action.deadline_alternatives = valid
        deadline = normalized(action.deadline_text or "")
        if valid and deadline and not any(deadline in normalized(item.text) or normalized(item.text) in deadline for item in valid):
            source_id = next((segment_id for segment_id, text in sources.items() if deadline in text), None)
            if source_id and len(valid) < 20:
                valid.append(DeadlineAlternative(text=action.deadline_text, segment_id=source_id))
            action.deadline_resolution = "conflict"
        if len(valid) > 1:
            action.deadline_resolution = "conflict"
        if action.deadline_resolution == "conflict":
            action.due_date = None
            action.needs_review = True
    analysis.decisions = list(dict.fromkeys(analysis.decisions))
    return analysis
