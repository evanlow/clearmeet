"""
MOM validation logic.

Enforces checklist validation before export.
"""
from typing import Union
from dataclasses import dataclass

from core.schema import MeetingMOM


@dataclass
class ValidationItem:
    """Single validation checklist item."""
    id: str
    label: str
    required: bool = True
    checked: bool = False


class MOMValidator:
    """Validate MOM completeness and quality."""

    @staticmethod
    def compute_validation_issues(mom: MeetingMOM, mom_text: str) -> list[str]:
        """
        Compute validation issues for a MOM.

        Args:
            mom: MeetingMOM object (can be model_constructed)
            mom_text: Full MOM or transcript text to scan

        Returns:
            List of issue messages
        """
        issues = []

        objective = (mom.objective or "").strip() if hasattr(mom, "objective") else ""
        if not objective:
            issues.append("Meeting objective is missing")

        decisions = getattr(mom, "decisions", []) or []
        notes = (getattr(mom, "notes", "") or "").lower()
        decision_note_present = "no decision" in notes or "no decisions" in notes
        if not decisions and not decision_note_present:
            issues.append("No decisions documented (note explicitly if none were made)")

        action_items = getattr(mom, "action_items", []) or []
        for index, item in enumerate(action_items, start=1):
            if isinstance(item, dict):
                owner = (item.get("owner") or "").strip()
                deadline = (item.get("deadline") or "").strip()
            else:
                owner = (getattr(item, "owner", "") or "").strip()
                deadline = (getattr(item, "deadline", "") or "").strip()

            if not owner:
                issues.append(f"Action item {index} is missing an owner")
            if not deadline:
                issues.append(f"Action item {index} is missing a deadline")

        scan_text = (mom_text or "").lower()
        confidential_markers = ["$", "sgd", "usd", "confidential", "salary", "nric", "bank"]
        if any(marker in scan_text for marker in confidential_markers):
            issues.append("Potential confidential information detected (review before circulation)")

        return issues
    
    @staticmethod
    def get_validation_checklist() -> list[ValidationItem]:
        """
        Get standard MOM validation checklist.
        
        Returns:
            List of validation items
        """
        return [
            ValidationItem(
                id="decisions_captured",
                label="Decisions accurately captured",
                required=True
            ),
            ValidationItem(
                id="action_items_owners",
                label="All action items have owners",
                required=True
            ),
            ValidationItem(
                id="action_items_deadlines",
                label="All action items have deadlines",
                required=True
            ),
            ValidationItem(
                id="no_confidential_info",
                label="No confidential information included",
                required=True
            ),
            ValidationItem(
                id="ready_within_24h",
                label="Ready to circulate within 24 hours",
                required=True
            ),
        ]
    
    @staticmethod
    def validate_mom_content(mom_data: Union[dict, MeetingMOM]) -> tuple[bool, list[str]]:
        """
        Validate MOM content for completeness.
        
        Args:
            mom_data: Structured MOM data
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if isinstance(mom_data, MeetingMOM):
            mom_data = mom_data.model_dump(exclude_none=True)
        
        # Check title
        if not mom_data.get('title') or len(mom_data['title'].strip()) < 3:
            issues.append("Meeting title is missing or too short")

        # Check date
        if not mom_data.get('date') or len(mom_data['date'].strip()) < 4:
            issues.append("Meeting date is missing or too short")

        # Check objective
        if not mom_data.get('objective') or len(mom_data['objective'].strip()) < 10:
            issues.append("Meeting objective is missing or too short")
        
        # Check attendees (optional but recommended)
        if mom_data.get('attendees') is not None and len(mom_data.get('attendees', [])) == 0:
            issues.append("Attendees list is present but empty")
        
        # Check decisions
        if not mom_data.get('decisions') or len(mom_data['decisions']) == 0:
            issues.append("No decisions documented (if no decisions were made, note that explicitly)")
        
        # Check action items
        action_items = mom_data.get('action_items', [])
        if action_items:
            for i, item in enumerate(action_items, 1):
                if not item.get('action') or len(item['action'].strip()) < 3:
                    issues.append(f"Action item {i} has missing or unclear action")
                if not item.get('owner') or item['owner'].strip() in ['', 'N/A', 'None', 'Unassigned']:
                    issues.append(f"Action item {i} has no owner assigned")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    @staticmethod
    def validate_checklist(checklist: list[ValidationItem]) -> tuple[bool, list[str]]:
        """
        Validate that all required checklist items are checked.
        
        Args:
            checklist: List of validation items
            
        Returns:
            Tuple of (all_required_checked, list_of_unchecked_required_items)
        """
        unchecked_required = []
        
        for item in checklist:
            if item.required and not item.checked:
                unchecked_required.append(item.label)
        
        all_checked = len(unchecked_required) == 0
        return all_checked, unchecked_required
    
    @staticmethod
    def validate_text_length(text: str, min_length: int = 100) -> tuple[bool, str]:
        """
        Validate MOM text meets minimum length requirements.
        
        Args:
            text: MOM text
            min_length: Minimum character count
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "MOM text is empty"
        
        if len(text) < min_length:
            return False, f"MOM is too short (minimum {min_length} characters, got {len(text)})"
        
        return True, ""
