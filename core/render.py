"""
MOM rendering and edit-application helpers.
"""
from datetime import datetime, timezone
from typing import Optional
import textwrap

from core.schema import MeetingMOM, ActionItem


def _format_action_cell(value: str, width: int) -> str:
    text = (value or "").strip()
    if len(text) > width:
        text = text[: width - 3] + "..."
    return text.ljust(width)


def _wrap_action_text(value: str, width: int) -> list[str]:
    text = (value or "").strip()
    wrapped = textwrap.wrap(text, width=width) if text else [""]
    return wrapped or [""]


def format_action_items(action_items: list[ActionItem]) -> list[str]:
    """
    Format action items in a compact table-like style.

    Args:
        action_items: List of typed action items

    Returns:
        List of output lines
    """
    if not action_items:
        return ["  None"]

    action_width = 34
    owner_width = 18
    deadline_width = 24
    status_width = 12

    lines = []
    header = (
        f"  {'#':<3}| "
        f"{_format_action_cell('Action', action_width)} | "
        f"{_format_action_cell('Owner', owner_width)} | "
        f"{_format_action_cell('Deadline', deadline_width)} | "
        f"{_format_action_cell('Status', status_width)}"
    )
    divider = (
        f"  {'-' * 3}+"
        f"-{'-' * action_width}-+-"
        f"{'-' * owner_width}-+-"
        f"{'-' * deadline_width}-+-"
        f"{'-' * status_width}"
    )

    lines.append(header)
    lines.append(divider)

    for index, item in enumerate(action_items, start=1):
        deadline = item.deadline if item.deadline else "No deadline specified"
        owner = item.owner if item.owner else "Unassigned"
        status = item.status if item.status else "Open"
        action_lines = _wrap_action_text(item.action, action_width)

        for line_index, action_line in enumerate(action_lines):
            if line_index == 0:
                lines.append(
                    f"  {index:<3}| "
                    f"{_format_action_cell(action_line, action_width)} | "
                    f"{_format_action_cell(owner, owner_width)} | "
                    f"{_format_action_cell(deadline, deadline_width)} | "
                    f"{_format_action_cell(status, status_width)}"
                )
            else:
                lines.append(
                    f"  {'':<3}| "
                    f"{_format_action_cell(action_line, action_width)} | "
                    f"{_format_action_cell('', owner_width)} | "
                    f"{_format_action_cell('', deadline_width)} | "
                    f"{_format_action_cell('', status_width)}"
                )

    return lines


def mom_to_text(mom: MeetingMOM, agenda_items: Optional[list[dict]] = None) -> str:
    """
    Render a typed MOM object into corporate MOM text format.

    Args:
        mom: Validated MeetingMOM instance
        agenda_items: Optional list of planned agenda items (dicts with title, duration_minutes, description)

    Returns:
        Formatted MOM text
    """
    attendees = mom.attendees or []
    parking_lot = mom.parking_lot or []

    lines = [
        "MINUTES OF MEETING",
        "=" * 72,
        f"Title: {mom.title}",
        f"Date: {mom.date}",
    ]

    # Add time information if available
    if mom.start_time or mom.end_time:
        time_info = ""
        if mom.start_time:
            time_info = f"Start: {mom.start_time}"
        if mom.end_time:
            if time_info:
                time_info += f" | End: {mom.end_time}"
            else:
                time_info = f"End: {mom.end_time}"
        if time_info:
            lines.append(time_info)

    # Add venue if available
    if mom.venue:
        lines.append(f"Venue: {mom.venue}")

    lines.extend(["", "Objective:", f"  {mom.objective}", ""])
    lines.append("Attendees:")

    if attendees:
        for attendee in attendees:
            lines.append(f"  - {attendee}")
    else:
        lines.append("  None")

    # Phase 2 Integration: Add Agenda section if available
    if agenda_items:
        lines.append("")
        lines.append("Planned Agenda:")
        total_duration = 0
        for idx, item in enumerate(agenda_items, 1):
            duration = item.get('duration_minutes', 0)
            total_duration += duration
            lines.append(f"  {idx}. {item.get('title', '')} ({duration}min)")
            if item.get('description'):
                lines.append(f"     {item.get('description')}")
        lines.append(f"  Total: {total_duration}min")

    lines.append("")
    lines.append("Key Decisions:")
    if mom.decisions:
        for index, decision in enumerate(mom.decisions, start=1):
            lines.append(f"  {index}. {decision.text}")
    else:
        lines.append("  None")

    lines.append("")
    lines.append("Action Items:")
    lines.extend(format_action_items(mom.action_items))

    # Only include Parking Lot section if there are items
    if parking_lot:
        lines.append("")
        lines.append("Parking Lot:")
        for index, item in enumerate(parking_lot, start=1):
            lines.append(f"  {index}. {item}")

    # Only include Notes section if there is content
    if mom.notes:
        lines.append("")
        lines.append("Notes:")
        lines.append(f"  {mom.notes}")

    lines.append("")

    audit_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(f"Audit: Generated by ClearMeet from structured MOM at {audit_time}")

    return "\n".join(lines)


def apply_user_edits(structured: MeetingMOM, edited_text: str) -> MeetingMOM:
    """
    Apply user edits to MOM for MVP behavior.

    For MVP, structured fields remain unchanged. The caller stores edited_text
    separately and may treat it as export truth.

    Args:
        structured: Validated MeetingMOM instance
        edited_text: User-edited full-text MOM

    Returns:
        Unchanged structured MeetingMOM
    """
    _ = edited_text
    return structured
