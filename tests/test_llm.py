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
from unittest.mock import Mock, patch, MagicMock
from core.llm import MOMGenerator
from core.schema import validate_mom_dict


class TestMOMGenerator:
    """Test suite for MOMGenerator class."""
    
    @pytest.fixture
    def mock_api_key(self):
        """Provide test API key."""
        return "test-api-key-12345"
    
    @pytest.fixture
    def generator(self, mock_api_key):
        """Create MOMGenerator instance for testing."""
        return MOMGenerator(api_key=mock_api_key, model="gpt-4o-mini", temperature=0.3)
    
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
    
    def test_initialization_with_valid_key(self, mock_api_key):
        """Test successful initialization with API key."""
        generator = MOMGenerator(api_key=mock_api_key)
        assert generator.model == "gpt-4o-mini"
        assert generator.temperature == 0.3
    
    def test_initialization_without_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="API key is required"):
            MOMGenerator(api_key="")
    
    def test_initialization_with_none_key_raises_error(self):
        """Test that None API key raises ValueError."""
        with pytest.raises(ValueError, match="API key is required"):
            MOMGenerator(api_key=None)
    
    def test_initialization_with_custom_params(self, mock_api_key):
        """Test initialization with custom model and temperature."""
        generator = MOMGenerator(api_key=mock_api_key, model="gpt-4", temperature=0.7)
        assert generator.model == "gpt-4"
        assert generator.temperature == 0.7
    
    @patch('core.llm.OpenAI')
    def test_generate_mom_with_valid_transcript(self, mock_openai_class, generator, sample_transcript, sample_mom_data):
        """Test MOM generation with valid transcript."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(sample_mom_data)
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        generator.client = mock_client
        
        # Generate MOM
        result = generator.generate_mom(sample_transcript)
        
        # Verify structure
        assert isinstance(result, dict)
        assert "title" in result
        assert "date" in result
        assert "objective" in result
        assert "decisions" in result
        assert "action_items" in result
        assert "attendees" in result
    
    def test_generate_mom_raises_error_with_empty_transcript(self, generator):
        """Test that empty transcript raises ValueError."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            generator.generate_mom("")
    
    def test_generate_mom_raises_error_with_none_transcript(self, generator):
        """Test that None transcript raises ValueError."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            generator.generate_mom(None)
    
    @patch('core.llm.OpenAI')
    def test_generate_mom_with_additional_context(self, mock_openai_class, generator, sample_transcript, sample_mom_data):
        """Test MOM generation with additional context."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(sample_mom_data)
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        generator.client = mock_client
        
        context = "Weekly team meeting for Q1 planning"
        result = generator.generate_mom(sample_transcript, additional_context=context)
        
        # Verify API was called with context
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert any(context in msg['content'] for msg in messages)
    
    @patch('core.llm.OpenAI')
    def test_generate_mom_handles_invalid_json_response(self, mock_openai_class, generator, sample_transcript):
        """Test handling of invalid JSON from API."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Not valid JSON at all"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        generator.client = mock_client
        
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            generator.generate_mom(sample_transcript)
    
    @patch('core.llm.OpenAI')
    def test_generate_mom_handles_empty_api_response(self, mock_openai_class, generator, sample_transcript):
        """Test handling of empty response from API."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        generator.client = mock_client
        
        with pytest.raises(ValueError, match="Empty response from API"):
            generator.generate_mom(sample_transcript)
    
    def test_validate_mom_structure_with_valid_data(self, sample_mom_data):
        """Test validation accepts valid MOM structure."""
        # Should not raise ValidationError
        validated = validate_mom_dict(sample_mom_data)
        assert validated is not None
        assert validated.objective == sample_mom_data['objective']
    
    def test_validate_mom_structure_rejects_missing_keys(self):
        """Test validation rejects data with missing keys."""
        incomplete_data = {
            "title": "Test Meeting",
            "objective": "Test objective",
            "decisions": []
            # Missing date, action_items
        }
        with pytest.raises(ValueError):
            validate_mom_dict(incomplete_data)
    
    def test_validate_mom_structure_rejects_wrong_types(self):
        """Test validation rejects data with wrong types."""
        wrong_types = {
            "title": "Test Meeting",
            "date": "2026-02-16",
            "objective": "Test",
            "decisions": "Should be a list",  # Wrong type
            "action_items": [],
            "attendees": []
        }
        with pytest.raises(ValueError):
            validate_mom_dict(wrong_types)
    
    def test_validate_mom_structure_validates_action_items(self):
        """Test validation checks action item structure."""
        invalid_action_items = {
            "title": "Test Meeting",
            "date": "2026-02-16",
            "objective": "Test objective",
            "decisions": [],
            "action_items": [
                {"action": "Do something"}  # Missing owner
            ],
            "attendees": []
        }
        with pytest.raises(ValueError):
            validate_mom_dict(invalid_action_items)
    
    def test_render_mom_text_with_complete_data(self, sample_mom_data):
        """Test rendering complete MOM data to text."""
        generator = MOMGenerator(api_key="test-key")
        text = generator.render_mom_text(sample_mom_data)
        
        # Verify all sections present
        assert "MINUTES OF MEETING" in text
        assert "MEETING TITLE:" in text
        assert "MEETING DATE:" in text
        assert "MEETING OBJECTIVE:" in text
        assert "ATTENDEES:" in text
        assert "DECISIONS MADE:" in text
        assert "ACTION ITEMS:" in text
        
        # Verify content present
        assert sample_mom_data["objective"] in text
        assert sample_mom_data["decisions"][0]["text"] in text
        assert sample_mom_data["action_items"][0]["action"] in text
    
    def test_render_mom_text_handles_empty_data(self):
        """Test rendering with empty MOM data."""
        generator = MOMGenerator(api_key="test-key")
        text = generator.render_mom_text({})
        assert text == ""
    
    def test_render_mom_text_handles_none_data(self):
        """Test rendering with None data."""
        generator = MOMGenerator(api_key="test-key")
        text = generator.render_mom_text(None)
        assert text == ""
    
    def test_render_mom_text_formats_action_items_correctly(self, sample_mom_data):
        """Test that action items are formatted with owner and deadline."""
        generator = MOMGenerator(api_key="test-key")
        text = generator.render_mom_text(sample_mom_data)
        
        # Check first action item formatting
        assert "Owner: Carol" in text
        assert "Deadline: Friday" in text
    
    def test_render_mom_text_handles_missing_deadline(self):
        """Test rendering action item with null deadline."""
        generator = MOMGenerator(api_key="test-key")
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
        text = generator.render_mom_text(mom_data)
        assert "No deadline specified" in text
    
    def test_render_mom_text_with_empty_sections(self):
        """Test rendering with some empty sections."""
        generator = MOMGenerator(api_key="test-key")
        mom_data = {
            "title": "Test Meeting",
            "date": "2026-02-16",
            "objective": "Test objective",
            "decisions": [],  # Empty
            "action_items": [],  # Empty
            "attendees": []  # Empty
        }
        text = generator.render_mom_text(mom_data)
        
        # Should include non-empty sections
        assert "MEETING OBJECTIVE:" in text
        assert "Test objective" in text
        
        # Empty sections should not have content entries
        # (but headers may still appear depending on implementation)
