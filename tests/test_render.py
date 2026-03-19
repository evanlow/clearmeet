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
    assert "Parking Lot:" in text  # Sample MOM has parking_lot
    assert "Notes:" in text  # Sample MOM has notes
    assert "Audit:" in text


def test_format_action_items_handles_missing_fields_nicely():
    lines = format_action_items(_sample_mom().action_items)
    output = "\n".join(lines)

    assert "No deadline specified" in output
    assert "Unassigned" in output


def test_format_action_items_wraps_long_action_text():
    mom = _sample_mom()
    # Use a sentence long enough to exceed action_width=55 chars so wrapping is exercised
    mom.action_items[0].action = (
        "Scrub the contact list to remove duplicates before the campaign launch date arrives"
    )

    lines = format_action_items(mom.action_items)
    output = "\n".join(lines)

    assert "..." not in output
    assert "Scrub the contact list to remove duplicates" in output
    assert "campaign launch date arrives" in output


def test_apply_user_edits_keeps_structured_unchanged_for_mvp():
    structured = _sample_mom()
    edited_text = "User overrides text entirely in editor."

    result = apply_user_edits(structured, edited_text)

    assert result.model_dump() == structured.model_dump()


def test_mom_to_text_omits_empty_parking_lot():
    """Test that Parking Lot section is omitted when empty."""
    mom = _sample_mom()
    mom.parking_lot = None
    
    text = mom_to_text(mom)
    
    assert "Parking Lot:" not in text
    assert "Notes:" in text  # Notes should still be present


def test_mom_to_text_omits_empty_notes():
    """Test that Notes section is omitted when empty."""
    mom = _sample_mom()
    mom.notes = None
    
    text = mom_to_text(mom)
    
    assert "Parking Lot:" in text  # Parking Lot should still be present
    assert "Notes:" not in text


def test_mom_to_text_omits_both_when_empty():
    """Test that both Parking Lot and Notes sections are omitted when empty."""
    mom = _sample_mom()
    mom.parking_lot = None
    mom.notes = None
    
    text = mom_to_text(mom)
    
    assert "Parking Lot:" not in text
    assert "Notes:" not in text
    assert "Action Items:" in text  # Should still have required sections
    assert "Audit:" in text

def test_mom_to_text_includes_executive_summary_when_present():
    """Test that Executive Summary section appears when provided."""
    mom = _sample_mom()
    mom.executive_summary = "The team reviewed Q1 results and approved budget increase for Q2 marketing."
    
    text = mom_to_text(mom)
    
    assert "Executive Summary:" in text
    assert "The team reviewed Q1 results and approved budget increase for Q2 marketing." in text


def test_mom_to_text_omits_executive_summary_when_absent():
    """Test that Executive Summary section is omitted when not provided."""
    mom = _sample_mom()
    mom.executive_summary = None
    
    text = mom_to_text(mom)
    
    assert "Executive Summary:" not in text


def test_mom_to_text_includes_discussion_summary_when_present():
    """Test that Discussion Summary section appears when provided."""
    mom = _sample_mom()
    mom.discussion_summary = "The team discussed Q1 performance metrics and marketing ROI data."
    
    text = mom_to_text(mom)
    
    assert "Discussion Summary:" in text
    assert "The team discussed Q1 performance metrics and marketing ROI data." in text


def test_mom_to_text_omits_discussion_summary_when_absent():
    """Test that Discussion Summary section is omitted when not provided."""
    mom = _sample_mom()
    mom.discussion_summary = None
    
    text = mom_to_text(mom)
    
    assert "Discussion Summary:" not in text


def test_mom_to_text_includes_both_summaries():
    """Test that both summary sections appear when provided."""
    mom = _sample_mom()
    mom.executive_summary = "Executive summary here."
    mom.discussion_summary = "Discussion summary here."
    
    text = mom_to_text(mom)
    
    assert "Executive Summary:" in text
    assert "Executive summary here." in text
    assert "Discussion Summary:" in text
    assert "Discussion summary here." in text