"""
MOM validation logic.

Enforces checklist validation before export.
"""
from typing import Optional
from dataclasses import dataclass


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
                id="objective_present",
                label="Meeting objective is clearly stated",
                required=True
            ),
            ValidationItem(
                id="attendees_listed",
                label="All attendees are listed",
                required=True
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
    def validate_mom_content(mom_data: dict) -> tuple[bool, list[str]]:
        """
        Validate MOM content for completeness.
        
        Args:
            mom_data: Structured MOM data
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check objective
        if not mom_data.get('objective') or len(mom_data['objective'].strip()) < 10:
            issues.append("Meeting objective is missing or too short")
        
        # Check attendees
        if not mom_data.get('attendees') or len(mom_data['attendees']) == 0:
            issues.append("No attendees listed")
        
        # Check decisions
        if not mom_data.get('decisions') or len(mom_data['decisions']) == 0:
            issues.append("No decisions documented (if no decisions were made, note that explicitly)")
        
        # Check action items
        action_items = mom_data.get('action_items', [])
        if action_items:
            for i, item in enumerate(action_items, 1):
                if not item.get('task') or len(item['task'].strip()) < 5:
                    issues.append(f"Action item {i} has missing or unclear task")
                if not item.get('owner') or item['owner'].strip() in ['', 'N/A', 'None', 'Unassigned']:
                    issues.append(f"Action item {i} has no owner assigned")
        
        # Check summary
        if not mom_data.get('summary') or len(mom_data['summary'].strip()) < 20:
            issues.append("Meeting summary is missing or too brief")
        
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
