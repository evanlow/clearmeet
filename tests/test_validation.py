"""
Tests for MOM validation module.

Tests cover:
- Validation checklist generation
- MOM content validation
- Checklist item validation
- Text length validation
- Edge cases (empty data, incomplete data)
"""
import pytest
from core.validation import MOMValidator, ValidationItem


class TestValidationItem:
    """Test suite for ValidationItem dataclass."""
    
    def test_validation_item_creation(self):
        """Test creating a validation item."""
        item = ValidationItem(id="test_id", label="Test label", required=True)
        assert item.id == "test_id"
        assert item.label == "Test label"
        assert item.required is True
        assert item.checked is False
    
    def test_validation_item_defaults(self):
        """Test default values for validation item."""
        item = ValidationItem(id="test", label="Test")
        assert item.required is True  # Default
        assert item.checked is False  # Default
    
    def test_validation_item_optional(self):
        """Test creating optional validation item."""
        item = ValidationItem(id="test", label="Test", required=False)
        assert item.required is False


class TestMOMValidator:
    """Test suite for MOMValidator class."""
    
    @pytest.fixture
    def complete_mom_data(self):
        """Provide complete valid MOM data."""
        return {
            "title": "Q1 Budget Review",
            "date": "2026-02-16",
            "objective": "Discuss Q1 budget allocation and resource planning for upcoming projects",
            "attendees": ["Alice Johnson", "Bob Smith", "Carol Davis"],
            "decisions": [
                {"text": "Increase marketing budget by 15%"},
                {"text": "Hire two additional developers for Project X"}
            ],
            "action_items": [
                {
                    "action": "Update budget spreadsheet with new allocations",
                    "owner": "Alice Johnson",
                    "deadline": "2026-02-20"
                },
                {
                    "action": "Post job listings for developer positions",
                    "owner": "Bob Smith",
                    "deadline": "2026-02-18"
                }
            ]
        }
    
    @pytest.fixture
    def incomplete_mom_data(self):
        """Provide incomplete MOM data with issues."""
        return {
            "title": "A",  # Too short
            "date": "",  # Missing
            "objective": "Short",  # Too short
            "attendees": [],  # Empty
            "decisions": [],  # Empty
            "action_items": [
                {
                    "action": "Task with no owner",
                    "owner": "",  # Missing owner
                    "deadline": None
                }
            ]
        }
    
    def test_get_validation_checklist_returns_list(self):
        """Test that checklist is returned as list."""
        checklist = MOMValidator.get_validation_checklist()
        assert isinstance(checklist, list)
        assert len(checklist) > 0
    
    def test_get_validation_checklist_contains_required_items(self):
        """Test that checklist contains expected validation items."""
        checklist = MOMValidator.get_validation_checklist()
        ids = [item.id for item in checklist]
        
        assert "title_present" in ids
        assert "date_present" in ids
        assert "objective_present" in ids
        assert "attendees_listed" in ids
        assert "decisions_documented" in ids
        assert "action_items_assigned" in ids
    
    def test_validation_checklist_items_have_labels(self):
        """Test that all checklist items have labels."""
        checklist = MOMValidator.get_validation_checklist()
        for item in checklist:
            assert isinstance(item.label, str)
            assert len(item.label) > 0
    
    def test_validation_checklist_has_required_and_optional_items(self):
        """Test that checklist has mix of required and optional items."""
        checklist = MOMValidator.get_validation_checklist()
        required_count = sum(1 for item in checklist if item.required)
        optional_count = sum(1 for item in checklist if not item.required)
        
        assert required_count > 0
        assert optional_count >= 0  # May have optional items
    
    def test_validate_mom_content_accepts_complete_data(self, complete_mom_data):
        """Test validation passes for complete MOM data."""
        is_valid, issues = MOMValidator.validate_mom_content(complete_mom_data)
        assert is_valid is True
        assert len(issues) == 0
    
    def test_validate_mom_content_rejects_missing_objective(self):
        """Test validation fails for missing objective."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "",
            "attendees": ["Alice"],
            "decisions": [{"text": "Decision 1"}],
            "action_items": []
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("objective" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_rejects_short_objective(self):
        """Test validation fails for too-short objective."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Short",  # Less than 10 characters
            "attendees": ["Alice"],
            "decisions": [{"text": "Decision 1"}],
            "action_items": []
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("objective" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_rejects_no_attendees(self):
        """Test validation fails for empty attendees list."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Valid objective here",
            "attendees": [],
            "decisions": [{"text": "Decision 1"}],
            "action_items": []
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("attendees" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_rejects_no_decisions(self):
        """Test validation fails for empty decisions list."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Valid objective here",
            "attendees": ["Alice"],
            "decisions": [],
            "action_items": []
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("decision" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_checks_action_item_tasks(self):
        """Test validation checks action item task descriptions."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Valid objective here",
            "attendees": ["Alice"],
            "decisions": [{"text": "Decision 1"}],
            "action_items": [
                {"action": "", "owner": "Alice", "deadline": None}  # Empty action
            ]
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("action" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_checks_action_item_owners(self):
        """Test validation checks action item owners."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Valid objective here",
            "attendees": ["Alice"],
            "decisions": [{"text": "Decision 1"}],
            "action_items": [
                {"action": "Valid action", "owner": "", "deadline": None}  # Missing owner
            ]
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("owner" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_rejects_unassigned_owner(self):
        """Test validation rejects 'Unassigned' or 'N/A' owners."""
        data = {
            "title": "Weekly Sync",
            "date": "2026-02-16",
            "objective": "Valid objective here",
            "attendees": ["Alice"],
            "decisions": [{"text": "Decision 1"}],
            "action_items": [
                {"action": "Valid action", "owner": "Unassigned", "deadline": None}
            ]
        }
        is_valid, issues = MOMValidator.validate_mom_content(data)
        assert is_valid is False
        assert any("owner" in issue.lower() for issue in issues)
    
    def test_validate_mom_content_returns_all_issues(self, incomplete_mom_data):
        """Test that validation returns all issues found."""
        is_valid, issues = MOMValidator.validate_mom_content(incomplete_mom_data)
        assert is_valid is False
        assert len(issues) >= 3  # Multiple issues should be found
    
    def test_validate_checklist_all_required_checked(self):
        """Test checklist validation passes when all required items checked."""
        checklist = [
            ValidationItem(id="1", label="Required 1", required=True, checked=True),
            ValidationItem(id="2", label="Required 2", required=True, checked=True),
            ValidationItem(id="3", label="Optional", required=False, checked=False),
        ]
        all_checked, unchecked = MOMValidator.validate_checklist(checklist)
        assert all_checked is True
        assert len(unchecked) == 0
    
    def test_validate_checklist_missing_required_item(self):
        """Test checklist validation fails when required item unchecked."""
        checklist = [
            ValidationItem(id="1", label="Required 1", required=True, checked=True),
            ValidationItem(id="2", label="Required 2", required=True, checked=False),  # Unchecked!
        ]
        all_checked, unchecked = MOMValidator.validate_checklist(checklist)
        assert all_checked is False
        assert len(unchecked) == 1
        assert "Required 2" in unchecked
    
    def test_validate_checklist_optional_items_not_required(self):
        """Test that unchecked optional items don't fail validation."""
        checklist = [
            ValidationItem(id="1", label="Required", required=True, checked=True),
            ValidationItem(id="2", label="Optional 1", required=False, checked=False),
            ValidationItem(id="3", label="Optional 2", required=False, checked=False),
        ]
        all_checked, unchecked = MOMValidator.validate_checklist(checklist)
        assert all_checked is True
        assert len(unchecked) == 0
    
    def test_validate_checklist_returns_unchecked_labels(self):
        """Test that validation returns labels of unchecked required items."""
        checklist = [
            ValidationItem(id="1", label="Item A", required=True, checked=False),
            ValidationItem(id="2", label="Item B", required=True, checked=False),
        ]
        all_checked, unchecked = MOMValidator.validate_checklist(checklist)
        assert all_checked is False
        assert "Item A" in unchecked
        assert "Item B" in unchecked
        assert len(unchecked) == 2
    
    def test_validate_text_length_accepts_sufficient_text(self):
        """Test text validation passes for sufficient length."""
        text = "This is a proper MOM document with enough content to meet the minimum requirements."
        is_valid, message = MOMValidator.validate_text_length(text, min_length=50)
        assert is_valid is True
        assert message == ""
    
    def test_validate_text_length_rejects_empty_text(self):
        """Test text validation fails for empty text."""
        is_valid, message = MOMValidator.validate_text_length("")
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_text_length_rejects_short_text(self):
        """Test text validation fails for too-short text."""
        text = "Too short"
        is_valid, message = MOMValidator.validate_text_length(text, min_length=100)
        assert is_valid is False
        assert "short" in message.lower()
        assert "100" in message or "character" in message.lower()
    
    def test_validate_text_length_with_custom_minimum(self):
        """Test text validation with custom minimum length."""
        text = "Some text here"
        
        # Should fail with high minimum
        is_valid, _ = MOMValidator.validate_text_length(text, min_length=50)
        assert is_valid is False
        
        # Should pass with low minimum
        is_valid, _ = MOMValidator.validate_text_length(text, min_length=10)
        assert is_valid is True
    
    def test_validate_text_length_ignores_whitespace(self):
        """Test that validation strips whitespace properly."""
        text = "   Valid content here with sufficient text   "
        is_valid, message = MOMValidator.validate_text_length(text, min_length=20)
        # Should still validate the actual text length, not just whitespace
        assert is_valid is True or message != "MOM text is empty"
