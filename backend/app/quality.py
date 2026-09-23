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


def recover_explicit_owner(action, segments):
    if action.owner:
        return
    candidates = []
    for segment in segments:
        if segment.id not in action.segment_ids or normalized(segment.text) not in normalized(action.evidence):
            continue
        match = re.match(r"^\s*([А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]*(?:ович|евич|овна|евна)),\s*(.*)", segment.text, re.DOTALL)
        if not match:
            continue
        address, instruction = match.groups()
        direct = re.match(r"(?:пожалуйста,?\s+)?(?:подготовьте|проведите|организуйте|соберите|свяжитесь|проверьте|направьте)\b", instruction, re.IGNORECASE)
        followup = re.match(r"ну-ка,\s*подскажите\b", instruction, re.IGNORECASE) and re.search(r"\bвот и проводите,\s*ждем от вас\b", instruction, re.IGNORECASE)
        other_address = re.search(r"[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]*(?:ович|евич|овна|евна),", instruction)
        if (direct or followup) and not other_address:
            candidates.append((address, segment.text))
            continue
        vocative = re.match(
            r"^\s*([А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+ович)а?,\s*"
            r"свяжитесь с ([А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+ович)(?:ем|ом)\b",
            segment.text,
        )
        if vocative and normalized(vocative.group(1)) == normalized(vocative.group(2)):
            candidates.append((vocative.group(1), segment.text))
    positions = {segment.id: index for index, segment in enumerate(segments)}
    action_positions = [positions[item] for item in action.segment_ids if item in positions]
    for left_index, right_index in zip(action_positions, action_positions[1:]):
        if right_index != left_index + 1:
            continue
        joined = f"{segments[left_index].text} {segments[right_index].text}"
        if normalized(joined) not in normalized(action.evidence):
            continue
        continuation = re.match(
            r"^\s*[А-ЯЁ][а-яё-]+\s+([А-ЯЁ][а-яё-]+ович)а?,\s*"
            r"свяжитесь с ([А-ЯЁ][а-яё-]+)\s+([А-ЯЁ][а-яё-]+ович)(?:ем|ом)\b",
            joined,
        )
        if continuation and normalized(continuation.group(1)) == normalized(continuation.group(3)):
            given_name = re.sub(r"(?:ом|ем)$", "", continuation.group(2), flags=re.IGNORECASE)
            candidates.append((f"{given_name} {continuation.group(3)}", joined))
    if len(candidates) == 1:
        action.owner, action.owner_evidence = candidates[0]
        action.owner_uncertain = True
        action.needs_review = True
        question = "Исполнитель восстановлен из явного обращения в ASR. Подтвердите имя и адресата по аудио."
        if question not in action.review_questions and len(action.review_questions) < 30:
            action.review_questions.append(question)


def summary_coverage(summary, segments):
    return {fragment.segment_id + "\n" + fragment.text for fragment in numeric_fragments(segments, summary) if fragment.included}


def prefer_summary(previous, candidate, segments):
    previous_coverage = summary_coverage(previous, segments)
    candidate_coverage = summary_coverage(candidate, segments)
    marker = "[Цитата не совпала с источником — требуется проверка]"
    if candidate_coverage > previous_coverage and candidate.count(marker) <= previous.count(marker):
        return candidate
    return previous


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
