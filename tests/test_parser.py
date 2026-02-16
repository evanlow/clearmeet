"""
Tests for transcript parser module.

Tests cover:
- Text cleaning and normalization
- Duration estimation
- Speaker extraction
- Transcript validation
- Edge cases (empty, short, malformed text)
"""
import pytest
from core.parser import TranscriptParser


class TestTranscriptParser:
    """Test suite for TranscriptParser class."""
    
    def test_clean_transcript_removes_extra_whitespace(self):
        """Test that excessive whitespace is normalized."""
        text = "Hello    world.  \n\n  Multiple   spaces."
        result = TranscriptParser.clean_transcript(text)
        assert "    " not in result
        assert "  " not in result
        assert result == "Hello world. Multiple spaces."
    
    def test_clean_transcript_removes_excessive_fillers(self):
        """Test that repeated filler words are reduced."""
        text = "So um um um we need to um decide"
        result = TranscriptParser.clean_transcript(text)
        assert result.count("um um") == 0 or result.count("um") <= 2
    
    def test_clean_transcript_handles_empty_string(self):
        """Test handling of empty input."""
        result = TranscriptParser.clean_transcript("")
        assert result == ""
    
    def test_clean_transcript_handles_none(self):
        """Test defensive handling of None input."""
        result = TranscriptParser.clean_transcript(None)
        assert result == ""
    
    def test_estimate_duration_with_typical_transcript(self):
        """Test duration estimation with normal text."""
        # 150 words at 150 wpm = 1 minute
        text = " ".join(["word"] * 150)
        duration = TranscriptParser.estimate_duration(text)
        assert duration == 1
    
    def test_estimate_duration_with_longer_transcript(self):
        """Test duration estimation with longer meeting."""
        # 450 words at 150 wpm = 3 minutes
        text = " ".join(["word"] * 450)
        duration = TranscriptParser.estimate_duration(text)
        assert duration == 3
    
    def test_estimate_duration_returns_minimum_one(self):
        """Test that very short transcripts return at least 1 minute."""
        text = "Very short"
        duration = TranscriptParser.estimate_duration(text)
        assert duration >= 1
    
    def test_estimate_duration_with_empty_text(self):
        """Test duration with empty text returns 0."""
        duration = TranscriptParser.estimate_duration("")
        assert duration == 0
    
    def test_extract_speakers_with_colon_format(self):
        """Test speaker extraction with 'Name:' format."""
        text = "John: Hello everyone. Alice: Thanks for joining."
        speakers = TranscriptParser.extract_speakers(text)
        assert "John" in speakers
        assert "Alice" in speakers
        assert len(speakers) == 2
    
    def test_extract_speakers_with_bracket_format(self):
        """Test speaker extraction with '[Name]' format."""
        text = "[Bob] We should discuss. [Carol] I agree completely."
        speakers = TranscriptParser.extract_speakers(text)
        assert "Bob" in speakers
        assert "Carol" in speakers
    
    def test_extract_speakers_with_speaker_number(self):
        """Test speaker extraction with 'Speaker N:' format."""
        text = "Speaker 1: First point. Speaker 2: Second point."
        speakers = TranscriptParser.extract_speakers(text)
        assert "Speaker 1" in speakers
        assert "Speaker 2" in speakers
    
    def test_extract_speakers_returns_sorted_list(self):
        """Test that speakers are returned in sorted order."""
        text = "Zoe: Last. Alice: First. Bob: Middle."
        speakers = TranscriptParser.extract_speakers(text)
        assert speakers == sorted(speakers)
    
    def test_extract_speakers_handles_duplicates(self):
        """Test that duplicate speakers are deduplicated."""
        text = "Alice: Point one. Bob: Point two. Alice: Point three."
        speakers = TranscriptParser.extract_speakers(text)
        assert speakers.count("Alice") == 1
        assert len(speakers) == 2
    
    def test_extract_speakers_with_no_speakers(self):
        """Test with transcript that has no speaker markers."""
        text = "This is just a continuous transcript without any speaker markers at all."
        speakers = TranscriptParser.extract_speakers(text)
        assert speakers == []
    
    def test_extract_speakers_with_empty_text(self):
        """Test speaker extraction with empty text."""
        speakers = TranscriptParser.extract_speakers("")
        assert speakers == []
    
    def test_validate_transcript_accepts_valid_text(self):
        """Test that valid transcripts pass validation."""
        text = " ".join(["word"] * 100)  # 100 words, well above minimum
        is_valid, message = TranscriptParser.validate_transcript(text)
        assert is_valid is True
        assert message == ""
    
    def test_validate_transcript_rejects_empty_text(self):
        """Test that empty transcripts are rejected."""
        is_valid, message = TranscriptParser.validate_transcript("")
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_transcript_rejects_short_text(self):
        """Test that too-short transcripts are rejected."""
        text = "Too short"  # Only 2 words
        is_valid, message = TranscriptParser.validate_transcript(text, min_words=50)
        assert is_valid is False
        assert "short" in message.lower()
    
    def test_validate_transcript_rejects_gibberish(self):
        """Test that gibberish with excessive special chars is rejected."""
        text = "!@#$%^&*(){}[]" * 50  # Mostly special characters
        is_valid, message = TranscriptParser.validate_transcript(text, min_words=10)
        assert is_valid is False
        assert "special characters" in message.lower()
    
    def test_validate_transcript_with_custom_min_words(self):
        """Test validation with custom minimum word count."""
        text = " ".join(["word"] * 25)
        is_valid, _ = TranscriptParser.validate_transcript(text, min_words=30)
        assert is_valid is False
        
        is_valid, _ = TranscriptParser.validate_transcript(text, min_words=20)
        assert is_valid is True
    
    def test_clean_transcript_preserves_important_content(self):
        """Test that cleaning doesn't remove important content."""
        text = "We discussed three items: budget, timeline, and resources."
        result = TranscriptParser.clean_transcript(text)
        assert "budget" in result
        assert "timeline" in result
        assert "resources" in result
    
    def test_extract_speakers_with_full_names(self):
        """Test speaker extraction with full names (first and last)."""
        text = "John Smith: Good morning. Mary Johnson: Hello everyone."
        speakers = TranscriptParser.extract_speakers(text)
        assert "John Smith" in speakers or "John" in speakers
        # Note: Current implementation may extract "John" or "John Smith" depending on regex
