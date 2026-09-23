import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["correction", "supplement", "speaker", "owner", "uncertain"]
    segment_id: str = Field(min_length=1, max_length=100)
    original: str = Field(default="", max_length=4000)
    text: str = Field(min_length=1, max_length=4000)
    action_id: str | None = Field(default=None, max_length=64)
    audio_checked: bool = False


class Glossary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    terms: list[str] = Field(default_factory=list, max_length=200)


class SourceReview(Glossary):
    notes: list[SourceNote] = Field(default_factory=list, max_length=200)


def validate_source_review(review, segments, actions):
    indexed = {segment["id"]: segment for segment in segments}
    action_ids = {action.id for action in actions}
    if any(not term.strip() or len(term) > 200 for term in review.terms):
        raise ValueError("Термин должен содержать от 1 до 200 символов")
    seen = set()
    for note in review.notes:
        segment = indexed.get(note.segment_id)
        if segment is None:
            raise ValueError("Реплика не найдена")
        if not note.text.strip():
            raise ValueError("Укажите результат проверки")
        if note.kind != "uncertain" and not note.audio_checked:
            raise ValueError("Подтвердите прослушивание аудио или оставьте вопрос на проверке")
        if (note.kind == "correction" and not note.original.strip()) or (note.original and note.original not in segment["text"]):
            raise ValueError("Исходный фрагмент исправления должен точно совпадать с ASR")
        if note.kind == "owner" and note.action_id not in action_ids:
            raise ValueError("Выберите существующее поручение")
        if note.kind != "owner" and note.action_id is not None:
            raise ValueError("Ссылка на поручение допустима только для исполнителя")
        if note.kind in {"speaker", "owner"}:
            key = (note.kind, note.action_id if note.kind == "owner" else note.segment_id)
            if key in seen:
                raise ValueError("Для голоса или исполнителя оставьте одно подтверждение")
            seen.add(key)
            if len(note.text) > 200:
                raise ValueError("Имя не должно превышать 200 символов")
        if note.kind == "owner":
            action = next(action for action in actions if action.id == note.action_id)
            if action.owner != note.text:
                raise ValueError("Имя исполнителя в карточке не совпадает с подтверждением по аудио")


def distance(left, right):
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (left_char != right_char)))
        previous = current
    return previous[-1]


def suggestions(segments, terms):
    words = set(re.findall(r"[^\W\d_]+", " ".join(terms), re.UNICODE))
    candidates = sorted(word for word in words if 4 <= len(word) <= 80)
    normalized = {word.casefold() for word in candidates}
    result = []
    for segment in segments:
        for word in dict.fromkeys(re.findall(r"[^\W\d_]+", segment["text"], re.UNICODE)):
            source = word.casefold()
            if not 4 <= len(source) <= 80 or source in normalized:
                continue
            matches = [candidate for candidate in candidates if candidate[0].casefold() == source[0] and abs(len(candidate) - len(source)) <= 1 and distance(source, candidate.casefold()) <= 2]
            if matches:
                result.append({"segment_id": segment["id"], "original": word, "candidates": matches})
                if len(result) == 200:
                    return result
    return result


def review_lines(meeting):
    labels = {"correction": "Исправление ASR", "supplement": "Дополнение по аудио (не цитата ASR)", "speaker": "Говорящий этой реплики", "owner": "Исполнитель", "uncertain": "Нужно уточнить"}
    segments = {segment["id"]: segment for segment in meeting.get("segments", [])}
    lines = []
    for note in (meeting.get("source_review") or {}).get("notes", []):
        segment = segments.get(note["segment_id"], {})
        timestamp = segment.get("start")
        location = f"{note['segment_id']} / {timestamp:.1f} с" if timestamp is not None else note["segment_id"]
        original = f"«{note['original']}» → " if note["original"] else ""
        action = f" / поручение {note['action_id']}" if note.get("action_id") else ""
        lines.append(f"{labels[note['kind']]} [{location}{action}]: {original}{note['text']}")
    return lines
