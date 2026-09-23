"""GPU service client and alignment against original ASR word timestamps."""
import math

import httpx
from pydantic import BaseModel, Field, model_validator

from app.models import Segment


class Turn(BaseModel):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    speaker_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end <= self.start:
            raise ValueError("Invalid speaker interval")
        return self


def speaker_at(start, end, turns):
    totals = {}
    for turn in turns:
        overlap = max(0, min(end, turn.end) - max(start, turn.start))
        totals[turn.speaker_id] = totals.get(turn.speaker_id, 0) + overlap
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] <= 0:
        return None, True
    if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * .8:
        return None, True
    return ranked[0][0], False


def align_speakers(segments, turns):
    result = []
    for source in segments:
        if not source.words:
            # Older cached transcripts have no words: never fabricate word times.
            segment = source.model_copy(deep=True)
            if segment.start is not None and segment.end is not None:
                segment.speaker, segment.speaker_uncertain = speaker_at(segment.start, segment.end, turns)
            result.append(segment)
            continue
        group = []
        speaker, uncertain = None, False
        def flush():
            if group:
                result.append(Segment(id="", text=" ".join(w.word for w in group),
                    start=group[0].start, end=group[-1].end, speaker=speaker,
                    speaker_uncertain=uncertain, words=list(group)))
                group.clear()
        for word in source.words:
            label, ambiguous = speaker_at(word.start, word.end, turns)
            if group and (label != speaker or ambiguous != uncertain or word.start - group[-1].end > 1.5):
                flush()
            speaker, uncertain = label, ambiguous
            group.append(word)
            if word.word.endswith((".", "!", "?")) or len(group) >= 45:
                flush()
        flush()
    for index, segment in enumerate(result):
        segment.id = f"s{index + 1}"
    return result


async def remote_diarize(path, segments, settings):
    headers = {"Authorization": "Bearer " + settings.diarization_token} if settings.diarization_token else {}
    try:
        async with httpx.AsyncClient(timeout=settings.timeout, follow_redirects=False) as client:
            with path.open("rb") as audio:
                response = await client.post(settings.diarization_url + "/diarize",
                    headers=headers, files={"file": (path.name, audio)})
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        raise RuntimeError("Истёк таймаут диаризации. Повторите обработку: распознавание уже сохранено.") from None
    except httpx.HTTPStatusError as error:
        messages = {401: "Проверьте DIARIZATION_TOKEN.", 429: "GPU занят; повторите позже.",
                    503: "Модель на GPU ещё не готова.", 400: "Проверьте аудио и лимит 10 минут.",
                    413: "Запись превышает лимит GPU-сервиса (100 МБ)."}
        status = error.response.status_code
        raise RuntimeError(f"Диаризация: HTTP {status}. " + messages.get(status, "Повторите обработку.")) from None
    except httpx.RequestError:
        raise RuntimeError("Сервис диаризации недоступен. Проверьте SSH-туннель и повторите обработку.") from None
    except ValueError:
        raise RuntimeError("Сервис диаризации вернул некорректный JSON.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Сервис диаризации вернул некорректный ответ.")
    duration = payload.get("duration_seconds")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("Сервис диаризации вернул некорректную длительность")
    try:
        turns = [Turn.model_validate(item) for item in payload.get("turns", [])]
    except (ValueError, TypeError):
        raise RuntimeError("Сервис диаризации вернул некорректные интервалы.") from None
    if not turns or any(turn.end > duration + .1 for turn in turns):
        raise RuntimeError("Сервис диаризации не вернул корректные интервалы говорящих")
    metadata = {key: payload[key] for key in ("model", "duration_seconds", "elapsed_seconds") if key in payload}
    metadata["turns"] = [turn.model_dump() for turn in turns]
    return align_speakers(segments, turns), metadata
