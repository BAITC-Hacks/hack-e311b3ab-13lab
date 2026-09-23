"""Roles, permissions and the FastAPI dependencies that enforce them.

Global permissions come from the user's role. Access to a single meeting is decided by
`meeting_permissions`, which combines the role with the user's relation to the meeting:
creator, chair, participant or assignee of an action item.
"""

from enum import StrEnum

from fastapi import Depends, Header, HTTPException, Request


class Role(StrEnum):
    ADMIN = "admin"
    SECRETARY = "secretary"
    CHAIR = "chair"
    PARTICIPANT = "participant"
    AUDITOR = "auditor"


ROLE_LABELS = {
    Role.ADMIN: "Администратор",
    Role.SECRETARY: "Секретарь",
    Role.CHAIR: "Председатель",
    Role.PARTICIPANT: "Участник",
    Role.AUDITOR: "Аудитор",
}


class Permission(StrEnum):
    MANAGE_USERS = "users:manage"
    READ_DIRECTORY = "users:directory"
    READ_AUDIT = "audit:read"
    CREATE_MEETINGS = "meetings:create"


ROLE_PERMISSIONS = {
    Role.ADMIN: frozenset({Permission.MANAGE_USERS, Permission.READ_DIRECTORY, Permission.READ_AUDIT}),
    Role.SECRETARY: frozenset({Permission.CREATE_MEETINGS, Permission.READ_DIRECTORY}),
    Role.CHAIR: frozenset({Permission.CREATE_MEETINGS, Permission.READ_DIRECTORY}),
    Role.PARTICIPANT: frozenset(),
    Role.AUDITOR: frozenset({Permission.READ_AUDIT}),
}


class MeetingPermission(StrEnum):
    VIEW = "view"  # title, date, status
    READ = "read"  # summary, action items, transcript
    LISTEN = "listen"  # original recording
    EDIT = "edit"  # review draft, assign owners
    PEOPLE = "people"  # set chair and participants
    APPROVE = "approve"
    REOPEN = "reopen"
    TRACK = "track"  # change the status of any action item
    EXPORT = "export"  # DOCX, Markdown, PDF
    EXPORT_RAW = "export_raw"  # full JSON record
    RETRY = "retry"
    DELETE = "delete"


MP = MeetingPermission
ALL_MEETING_PERMISSIONS = frozenset(MeetingPermission)
CHAIR_PERMISSIONS = ALL_MEETING_PERMISSIONS - {MP.DELETE}
PUBLISHED_READER = frozenset({MP.VIEW, MP.READ, MP.EXPORT})


def role_permissions(user) -> frozenset:
    return ROLE_PERMISSIONS.get(user["role"], frozenset())


def assignee_ids(meeting) -> set:
    analysis = meeting.get("analysis") or {}
    return {action.get("assignee_id") for action in analysis.get("actions", []) if action.get("assignee_id")}


def meeting_permissions(user, meeting) -> frozenset:
    role = user["role"]
    if role == Role.SECRETARY:
        return ALL_MEETING_PERMISSIONS
    granted = set()
    if role in (Role.ADMIN, Role.AUDITOR):
        granted.add(MP.VIEW)
    if role == Role.ADMIN:
        granted.add(MP.DELETE)
    if role == Role.CHAIR and user["id"] in (meeting.get("created_by"), meeting.get("chair_id")):
        granted |= CHAIR_PERMISSIONS
    if meeting.get("status") == "approved":
        if user["id"] in meeting.get("participant_ids", []):
            granted |= PUBLISHED_READER
        if user["id"] in assignee_ids(meeting):
            granted.add(MP.VIEW)
    return frozenset(granted)


def current_user(request: Request, authorization: str = Header(default="")):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Требуется вход в систему", headers={"WWW-Authenticate": "Bearer"})
    user = request.app.state.store.session_user(token)
    if not user:
        raise HTTPException(401, "Сессия истекла. Войдите снова.", headers={"WWW-Authenticate": "Bearer"})
    request.state.token = token
    return user


def require(permission: Permission):
    def dependency(user=Depends(current_user)):
        if permission not in role_permissions(user):
            raise HTTPException(403, "Недостаточно прав")
        return user

    return dependency
