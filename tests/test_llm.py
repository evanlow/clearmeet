"""
Tests for LLM MOM generation module.

Tests cover:
- MOM generation from transcripts
- JSON structure validation
- Text rendering
- Error handling (API errors, invalid responses)
- Edge cases (empty input, malformed JSON)
"""
import pytest
import json
from unittest.mock import Mock, patch

from core.llm import extract_mom_from_transcript, render_mom_text
from core.schema import validate_mom_dict


class TestLLMFunctions:
    """Test suite for LLM helper functions."""

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        """Ensure required env vars are set for tests."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-12345")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("OPENAI_TEMPERATURE", "0.3")

    @pytest.fixture
    def sample_transcript(self):
        """Provide sample meeting transcript."""
        return """
        Alice: Good morning everyone. Today we need to decide on the Q1 budget allocation.
        Bob: I recommend increasing marketing spend by 15%.
        Alice: That makes sense. Let's also reduce travel expenses.
        Carol: I can work on the updated budget spreadsheet by Friday.
        Alice: Great. Bob, can you review the marketing strategy by Wednesday?
        Bob: Absolutely, I'll have it ready.
        """

    @pytest.fixture
    def sample_mom_data(self):
        """Provide sample structured MOM data."""
        return {
            "title": "Q1 Budget Meeting",
            "date": "2026-02-16",
            "objective": "Decide on Q1 budget allocation",
            "decisions": [
                {"text": "Increase marketing spend by 15%"},
                {"text": "Reduce travel expenses"}
            ],
            "action_items": [
                {
                    "action": "Update budget spreadsheet",
                    "owner": "Carol",
                    "deadline": "Friday"
                },
                {
                    "action": "Review marketing strategy",
                    "owner": "Bob",
                    "deadline": "Wednesday"
                }
            ],
            "attendees": ["Alice", "Bob", "Carol"]
        }

    @patch('core.llm.OpenAI')
    def test_extract_mom_with_valid_transcript(self, mock_openai_class, sample_transcript, sample_mom_data):
        """Test MOM extraction with valid transcript."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(sample_mom_data)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        result = extract_mom_from_transcript(sample_transcript)

        assert isinstance(result, dict)
        assert "title" in result
        assert "date" in result
        assert "objective" in result
        assert "decisions" in result
        assert "action_items" in result
        assert "attendees" in result

    def test_extract_mom_raises_error_with_empty_transcript(self):
        """Test that empty transcript raises ValueError."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            extract_mom_from_transcript("")

    @patch('core.llm.OpenAI')
    def test_extract_mom_retries_on_invalid_json(self, mock_openai_class, sample_transcript, sample_mom_data):
        """Test retry when the model returns invalid JSON."""
        invalid_response = Mock()
        invalid_response.choices = [Mock()]
        invalid_response.choices[0].message.content = "Not valid JSON"

        valid_response = Mock()
        valid_response.choices = [Mock()]
        valid_response.choices[0].message.content = json.dumps(sample_mom_data)

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = [invalid_response, valid_response]
        mock_openai_class.return_value = mock_client

        result = extract_mom_from_transcript(sample_transcript)
        assert result["title"] == sample_mom_data["title"]
        assert mock_client.chat.completions.create.call_count == 2

    @patch('core.llm.OpenAI')
    def test_extract_mom_rejects_invalid_structure(self, mock_openai_class, sample_transcript):
        """Test that invalid MOM structure raises ValueError."""
        invalid_data = {"title": "Test"}
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(invalid_data)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        with pytest.raises(ValueError, match="Invalid MOM structure"):
            extract_mom_from_transcript(sample_transcript)

    def test_validate_mom_structure_with_valid_data(self, sample_mom_data):
        """Test validation accepts valid MOM structure."""
        validated = validate_mom_dict(sample_mom_data)
        assert validated is not None
        assert validated.objective == sample_mom_data['objective']

    def test_validate_mom_structure_rejects_missing_keys(self):
        """Test validation rejects data with missing keys."""
        incomplete_data = {
            "title": "Test Meeting",
            "objective": "Test objective",
            "decisions": []
        }
        with pytest.raises(ValueError):
            validate_mom_dict(incomplete_data)

    @patch('core.llm.OpenAI')
    def test_missing_owner_adds_notes_and_flags(self, mock_openai_class, sample_transcript, sample_mom_data):
        """Test missing owners trigger notes and flags."""
        sample_mom_data["action_items"][0]["owner"] = ""
        sample_mom_data["action_items"][0]["deadline"] = ""

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(sample_mom_data)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        result = extract_mom_from_transcript(sample_transcript)

        assert "notes" in result
        assert "missing_owner" in result.get("confidentiality_flags", [])
        assert "missing_deadline" in result.get("confidentiality_flags", [])

    def test_render_mom_text_with_complete_data(self, sample_mom_data):
        """Test rendering complete MOM data to text."""
        text = render_mom_text(sample_mom_data)

        assert "MINUTES OF MEETING" in text
        assert "MEETING TITLE:" in text
        assert "MEETING DATE:" in text
        assert "MEETING OBJECTIVE:" in text
        assert "ATTENDEES:" in text
        assert "DECISIONS MADE:" in text
        assert "ACTION ITEMS:" in text
        assert sample_mom_data["objective"] in text
        assert sample_mom_data["decisions"][0]["text"] in text
        assert sample_mom_data["action_items"][0]["action"] in text

    def test_render_mom_text_handles_empty_data(self):
        """Test rendering with empty MOM data."""
        text = render_mom_text({})
        assert text == ""

    def test_render_mom_text_handles_none_data(self):
        """Test rendering with None data."""
        text = render_mom_text(None)
        assert text == ""

    def test_render_mom_text_handles_missing_deadline(self):
        """Test rendering action item with null deadline."""
        mom_data = {
            "title": "Test Meeting",
            "date": "2026-02-16",
            "objective": "Test",
            "decisions": [],
            "action_items": [
                {"action": "Do something", "owner": "Alice", "deadline": None}
            ],
            "attendees": ["Alice"]
        }
        text = render_mom_text(mom_data)
        assert "No deadline specified" in text
