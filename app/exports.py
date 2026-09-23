from io import BytesIO
from pathlib import Path

from docx import Document

STATUS_LABELS = {"open": "Открыто", "in_progress": "В работе", "done": "Выполнено"}


def _deadline(action):
    return action["due_date"] or action["deadline_text"] or "Не указан"


def _owner(action, people):
    owner = action["owner"] or "Не указан"
    assignee = people.get(action.get("assignee_id") or "")
    return f"{owner} → {assignee}" if assignee and assignee != action["owner"] else (assignee or owner)


def _approval_line(meeting, people):
    if meeting.get("status") == "approved" and meeting.get("approved_at"):
        return f"Протокол утверждён {meeting['approved_at'][:10]}: {people.get(meeting.get('approved_by') or '', 'пользователь удалён')}."
    return "Черновик ИИ. Требуется проверка секретарём."


def markdown(meeting, people=None):
    people = people or {}
    analysis = meeting["analysis"]
    lines = [f"# {meeting['title']}", "", f"Дата совещания: {meeting['meeting_date']}", "", _approval_line(meeting, people), ""]
    if meeting.get("chair_id") in people:
        lines += [f"Председатель: {people[meeting['chair_id']]}", ""]
    participants = [people[user_id] for user_id in meeting.get("participant_ids", []) if user_id in people]
    if participants:
        lines += [f"Участники: {', '.join(participants)}", ""]
    lines += ["## Саммари", analysis["summary"], "", "## Решения"]
    lines.extend(f"- {decision}" for decision in analysis["decisions"])
    lines += ["", "## Поручения"]
    for index, action in enumerate(analysis["actions"], 1):
        lines.extend([f"### {index}. {action['title']}", f"Ответственный: {_owner(action, people)}", f"Срок: {_deadline(action)}", f"Статус: {STATUS_LABELS.get(action['status'], action['status'])}", f"Цитата: {action['evidence']}", ""])
    lines += ["## Замечания"] + [f"- {warning}" for warning in analysis["warnings"]]
    lines += ["", "## Транскрипт", meeting["transcript"]]
    return "\n".join(lines)


def docx(meeting, people=None):
    people = people or {}
    document = Document()
    document.add_heading(meeting["title"], 0)
    document.add_paragraph(f"Дата совещания: {meeting['meeting_date']}")
    document.add_paragraph(_approval_line(meeting, people))
    if meeting.get("chair_id") in people:
        document.add_paragraph(f"Председатель: {people[meeting['chair_id']]}")
    participants = [people[user_id] for user_id in meeting.get("participant_ids", []) if user_id in people]
    if participants:
        document.add_paragraph(f"Участники: {', '.join(participants)}")
    analysis = meeting["analysis"]
    document.add_heading("Саммари", 1)
    document.add_paragraph(analysis["summary"])
    document.add_heading("Решения", 1)
    for decision in analysis["decisions"]:
        document.add_paragraph(decision, style="List Bullet")
    document.add_heading("Поручения", 1)
    table = document.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ["Поручение", "Ответственный", "Срок", "Статус"]):
        cell.text = label
    for action in analysis["actions"]:
        cells = table.add_row().cells
        cells[0].text = action["title"]
        cells[1].text = _owner(action, people)
        cells[2].text = _deadline(action)
        cells[3].text = STATUS_LABELS.get(action["status"], action["status"])
    document.add_heading("Основания и проверка", 1)
    for index, action in enumerate(analysis["actions"], 1):
        document.add_paragraph(f"{index}. {action['evidence']}")
        document.add_paragraph(f"Проверено: {'нет' if action['needs_review'] else 'да'}")
    for warning in analysis["warnings"]:
        document.add_paragraph(warning)
    document.add_heading("Транскрипт", 1)
    for segment in meeting["segments"]:
        speaker = meeting.get("speaker_names", {}).get(segment["speaker"], segment["speaker"]) or "Говорящий не определён"
        timestamp = f"[{segment['start']:.1f} с] " if segment["start"] is not None else ""
        document.add_paragraph(f"{timestamp}{speaker}: {segment['text']}")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", None),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]


def find_fonts(settings):
    """Return (regular, bold) TTF paths with Cyrillic glyphs, or None when PDF is unavailable."""
    candidates = [(settings.pdf_font_path, settings.pdf_font_bold_path or None)] if settings.pdf_font_path else FONT_CANDIDATES
    for regular, bold in candidates:
        if regular and Path(regular).is_file():
            return regular, bold if bold and Path(bold).is_file() else regular
    return None


def pdf(meeting, fonts, people=None):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    people = people or {}
    regular, bold = fonts
    document = FPDF()
    document.set_auto_page_break(True, margin=15)
    document.add_font("Main", "", regular)
    document.add_font("Main", "B", bold)
    document.set_title(meeting["title"])
    document.add_page()

    def paragraph(value, size=10, style="", gap=1.5):
        document.set_font("Main", style, size)
        document.multi_cell(0, size * 0.5, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        document.ln(gap)

    def heading(value):
        document.ln(2)
        paragraph(value, 13, "B", 1)

    analysis = meeting["analysis"]
    paragraph(meeting["title"], 18, "B", 2)
    paragraph(f"Дата совещания: {meeting['meeting_date']}")
    paragraph(_approval_line(meeting, people))
    if meeting.get("chair_id") in people:
        paragraph(f"Председатель: {people[meeting['chair_id']]}")
    participants = [people[user_id] for user_id in meeting.get("participant_ids", []) if user_id in people]
    if participants:
        paragraph(f"Участники: {', '.join(participants)}")
    heading("Саммари")
    paragraph(analysis["summary"] or "—")
    heading("Решения")
    for decision in analysis["decisions"] or ["—"]:
        paragraph(f"• {decision}")
    heading("Поручения")
    if analysis["actions"]:
        document.set_font("Main", "", 9)
        with document.table(col_widths=(8, 44, 22, 14, 12), text_align="LEFT", line_height=4.5) as table:
            header = table.row()
            for label in ("№", "Поручение", "Ответственный", "Срок", "Статус"):
                header.cell(label)
            for index, action in enumerate(analysis["actions"], 1):
                row = table.row()
                for value in (str(index), action["title"], _owner(action, people), _deadline(action), STATUS_LABELS.get(action["status"], action["status"])):
                    row.cell(value)
        heading("Основания")
        for index, action in enumerate(analysis["actions"], 1):
            paragraph(f"{index}. «{action['evidence']}» Проверено: {'нет' if action['needs_review'] else 'да'}.", 9)
    else:
        paragraph("Поручения не выделены.")
    if analysis["warnings"]:
        heading("Замечания")
        for warning in analysis["warnings"]:
            paragraph(f"• {warning}", 9)
    heading("Транскрипт")
    for segment in meeting["segments"]:
        speaker = meeting.get("speaker_names", {}).get(segment["speaker"], segment["speaker"]) or "Говорящий не определён"
        timestamp = f"[{segment['start']:.1f} с] " if segment["start"] is not None else ""
        paragraph(f"{timestamp}{speaker}: {segment['text']}", 9, gap=0.8)
    return bytes(document.output())
