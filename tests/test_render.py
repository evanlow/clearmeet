"""Tests for core render helpers."""

from core.render import mom_to_text, apply_user_edits, format_action_items
from core.schema import MeetingMOM


def _sample_mom() -> MeetingMOM:
    return MeetingMOM(
        title="Weekly Leadership Sync",
        date="2026-02-19",
        objective="Review delivery status and unblock key dependencies.",
        attendees=["Alice", "Bob"],
        decisions=[{"text": "Ship v1.2 on Friday"}],
        action_items=[
            {
                "action": "Finalize release notes",
                "owner": "Alice",
                "deadline": "2026-02-20",
                "status": "Open",
            },
            {
                "action": "Confirm QA sign-off",
                "owner": "",
                "deadline": None,
                "status": "In Progress",
            },
        ],
        parking_lot=["Q2 staffing plan"],
        notes="Escalate blocker to platform team if unresolved by noon.",
    )


def test_mom_to_text_includes_required_headings():
    text = mom_to_text(_sample_mom())

    assert "Title:" in text
    assert "Date:" in text
    assert "Objective:" in text
    assert "Attendees:" in text
    assert "Key Decisions:" in text
    assert "Action Items:" in text
    assert "Parking Lot:" in text
    assert "Notes:" in text
    assert "Audit:" in text


def test_format_action_items_handles_missing_fields_nicely():
    lines = format_action_items(_sample_mom().action_items)
    output = "\n".join(lines)

    assert "No deadline specified" in output
    assert "Unassigned" in output


def test_format_action_items_wraps_long_action_text():
    mom = _sample_mom()
    mom.action_items[0].action = "Scrub the contact list to reduce duplicates before the campaign launch"

    lines = format_action_items(mom.action_items)
    output = "\n".join(lines)

    assert "..." not in output
    assert "Scrub the contact list to reduce" in output
    assert "duplicates before the campaign" in output


def test_apply_user_edits_keeps_structured_unchanged_for_mvp():
    structured = _sample_mom()
    edited_text = "User overrides text entirely in editor."

    result = apply_user_edits(structured, edited_text)

    assert result.model_dump() == structured.model_dump()
