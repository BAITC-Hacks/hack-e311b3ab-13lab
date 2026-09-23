import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from app import exports
from app.config import Settings
from app.models import Analysis, Segment
from app.deadlines import ground_deadlines
from app.quality import numeric_fragments, validate_details, validate_summary_quotes
from app.pipeline import Provider


async def main():
    parser = argparse.ArgumentParser(description="Evaluate current LLM on cached ASR/diarization without modifying originals")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postprocess-only", action="store_true", help="Recheck a generated evaluation result without an LLM call; never use on manually edited protocols")
    parser.add_argument("--refresh-summary", action="store_true", help="Regenerate summary with validated action constraints")
    args = parser.parse_args()
    settings = Settings.from_env()
    args.output.mkdir(parents=True, exist_ok=True)
    provider = Provider(settings)
    for source in args.inputs:
        raw = source.read_bytes()
        meeting = json.loads(raw)
        segments = [Segment.model_validate(item) for item in meeting["segments"]]
        started = time.monotonic()
        if args.postprocess_only:
            analysis = ground_deadlines(validate_details(Analysis.model_validate(meeting["analysis"]), segments), meeting["meeting_date"])
            analysis.summary = validate_summary_quotes(analysis.summary, segments)
            analysis.numeric_fragments = numeric_fragments(segments, analysis.summary)
        else:
            analysis = await provider.analyze(segments, meeting["meeting_date"], meeting["title"])
        if args.refresh_summary:
            analysis.summary = await provider.summarize(segments, analysis.actions)
            analysis.numeric_fragments = numeric_fragments(segments, analysis.summary)
            if any(not item.included for item in analysis.numeric_fragments):
                analysis.warnings.append("Не все числовые фрагменты источника приведены дословно: проверьте показатели и контекст.")
        meeting["analysis"] = analysis.model_dump(mode="json")
        meeting["status"] = "ready"
        meeting["evaluation"] = {"source_sha256": hashlib.sha256(raw).hexdigest(), "text_model": meeting.get("evaluation", {}).get("text_model", settings.text_model) if args.postprocess_only else settings.text_model, "cached_asr_and_diarization": True, "postprocess_only": args.postprocess_only, "summary_refreshed": args.refresh_summary}
        output = args.output / source.stem
        if output.with_suffix(".json").resolve() == source.resolve():
            raise RuntimeError("Output must not overwrite the input")
        output.with_suffix(".json").write_text(json.dumps(meeting, ensure_ascii=False, indent=2))
        output.with_suffix(".md").write_text(exports.markdown(meeting))
        output.with_suffix(".docx").write_bytes(exports.docx(meeting))
        fonts = exports.find_fonts(settings)
        if fonts:
            output.with_suffix(".pdf").write_bytes(exports.pdf(meeting, fonts))
        if source.read_bytes() != raw:
            raise RuntimeError("Source changed during evaluation")
        print(json.dumps({"file": source.name, "seconds": round(time.monotonic() - started, 1), "actions": len(analysis.actions), "owners_unknown": sum(not action.owner for action in analysis.actions), "recovered_quotes": sum(bool(action.review_questions) for action in analysis.actions), "numeric_included": sum(fragment.included for fragment in analysis.numeric_fragments), "numeric_total": len(analysis.numeric_fragments), "warnings": analysis.warnings}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
