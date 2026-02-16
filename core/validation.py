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
    def get_validation_checklist() -> list[ValidationItem]:
        """
        Get standard MOM validation checklist.
        
        Returns:
            List of validation items
        """
        return [
            ValidationItem(
                id="title_present",
                label="Meeting title is clearly stated",
                required=True
            ),
            ValidationItem(
                id="date_present",
                label="Meeting date is provided",
                required=True
            ),
            ValidationItem(
                id="objective_present",
                label="Meeting objective is clearly stated",
                required=True
            ),
            ValidationItem(
                id="attendees_listed",
                label="All attendees are listed",
                required=False
            ),
            ValidationItem(
                id="decisions_documented",
                label="All decisions are documented",
                required=True
            ),
            ValidationItem(
                id="action_items_assigned",
                label="All action items have owners assigned",
                required=True
            ),
            ValidationItem(
                id="deadlines_specified",
                label="Deadlines are specified for time-sensitive items",
                required=False
            ),
            ValidationItem(
                id="language_professional",
                label="Language is professional and clear",
                required=True
            ),
            ValidationItem(
                id="reviewed_by_manager",
                label="Reviewed and approved by meeting organizer/manager",
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
