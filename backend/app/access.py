"""Loading meetings with a permission check and shaping them for API responses."""

from fastapi import HTTPException

from app.rbac import MeetingPermission as MP, assignee_ids, meeting_permissions

SUMMARY_FIELDS = ("id", "title", "meeting_date", "status", "created_at", "updated_at", "version", "error", "created_by", "chair_id", "participant_ids", "approved_at", "approved_by", "source", "live")
CONTENT_FIELDS = ("transcript", "segments", "analysis", "speaker_names", "participants_seen")
LIVE_PUBLIC_FIELDS = ("status", "detail", "connector", "platform", "started_at", "ended_at", "duration_seconds", "failed_windows", "bot_name", "stop_reason")


def load_meeting(store, meeting_id, user, needed=MP.VIEW):
    meeting = store.get(meeting_id)
    permissions = meeting_permissions(user, meeting) if meeting else frozenset()
    if MP.VIEW not in permissions:
        raise HTTPException(404, "Совещание не найдено")
    if needed not in permissions:
        raise HTTPException(403, "Недостаточно прав для этого действия")
    return meeting, permissions


def people_for(meeting, names):
    ids = {meeting.get("created_by"), meeting.get("chair_id"), meeting.get("approved_by"), *meeting.get("participant_ids", []), *assignee_ids(meeting)}
    ids |= {approval.get("approved_by") for approval in meeting.get("approvals", [])}
    return {user_id: names[user_id] for user_id in ids if user_id in names}


def present_meeting(store, meeting, permissions):
    result = {field: meeting.get(field) for field in SUMMARY_FIELDS}
    result["participant_ids"] = result["participant_ids"] or []
    result["source"] = result["source"] or {"type": "upload"}
    if result["live"]:
        result["live"] = {key: value for key, value in result["live"].items() if key in LIVE_PUBLIC_FIELDS}
    result["permissions"] = sorted(permissions)
    result["people"] = people_for(meeting, store.user_names())
    result["approvals"] = [{key: value for key, value in approval.items() if key != "files"} | {"formats": sorted(approval.get("files", {}))} for approval in meeting.get("approvals", [])]
    if MP.READ in permissions:
        result.update({field: meeting.get(field) for field in CONTENT_FIELDS})
        if result.get("participants_seen") is None:
            result["participants_seen"] = []
    return result
