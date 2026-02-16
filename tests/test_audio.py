"""
Tests for audio transcription module.

Tests cover:
- Audio file transcription
- File validation
- Error handling (missing files, invalid formats, oversized files)
- Edge cases (empty files, unsupported formats)
"""
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from core.audio import AudioTranscriber


class TestAudioTranscriber:
    """Test suite for AudioTranscriber class."""
    
    @pytest.fixture
    def mock_api_key(self):
        """Provide test API key."""
        return "test-api-key-12345"
    
    @pytest.fixture
    def transcriber(self, mock_api_key):
        """Create AudioTranscriber instance."""
        return AudioTranscriber(api_key=mock_api_key, model="whisper-1")
    
    def test_initialization_with_valid_key(self, mock_api_key):
        """Test successful initialization with API key."""
        transcriber = AudioTranscriber(api_key=mock_api_key)
        assert transcriber.model == "whisper-1"
    
    def test_initialization_without_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="API key is required"):
            AudioTranscriber(api_key="")
    
    def test_initialization_with_none_key_raises_error(self):
        """Test that None API key raises ValueError."""
        with pytest.raises(ValueError, match="API key is required"):
            AudioTranscriber(api_key=None)
    
    def test_initialization_with_custom_model(self, mock_api_key):
        """Test initialization with custom model."""
        transcriber = AudioTranscriber(api_key=mock_api_key, model="whisper-2")
        assert transcriber.model == "whisper-2"
    
    @patch('core.audio.OpenAI')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_transcribe_audio_with_valid_file(self, mock_file, mock_getsize, mock_exists, mock_openai_class, transcriber):
        """Test transcription with valid audio file."""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        
        mock_response = Mock()
        mock_response.text = "This is the transcribed text from the audio file."
        
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        transcriber.client = mock_client
        
        # Transcribe
        result = transcriber.transcribe_audio("test_audio.mp3")
        
        # Verify
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == "This is the transcribed text from the audio file."
    
    def test_transcribe_audio_raises_error_for_missing_file(self, transcriber):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            transcriber.transcribe_audio("nonexistent_file.mp3")
    
    @patch('os.path.exists')
    def test_transcribe_audio_raises_error_for_unsupported_format(self, mock_exists, transcriber):
        """Test that unsupported format raises ValueError."""
        mock_exists.return_value = True
        
        with pytest.raises(ValueError, match="Unsupported audio format"):
            transcriber.transcribe_audio("test_file.txt")
    
    @patch('core.audio.AudioTranscriber._transcribe_with_chunking')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    def test_transcribe_audio_triggers_chunking_for_large_file(self, mock_exists, mock_getsize, mock_chunk, transcriber):
        """Test that large files (>20MB) trigger chunking instead of raising error."""
        mock_exists.return_value = True
        mock_getsize.return_value = 30 * 1024 * 1024  # 30MB (over 20MB chunk threshold)
        mock_chunk.return_value = "Chunked transcript"
        
        result = transcriber.transcribe_audio("large_audio.mp3", chunk_size_mb=20)
        
        # Verify chunking was triggered
        mock_chunk.assert_called_once_with("large_audio.mp3", None, 20)
        assert result == "Chunked transcript"
    
    @patch('core.audio.OpenAI')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_transcribe_audio_with_language_parameter(self, mock_file, mock_getsize, mock_exists, mock_openai_class, transcriber):
        """Test transcription with language parameter."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024
        
        mock_response = Mock()
        mock_response.text = "Transcribed text"
        
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        transcriber.client = mock_client
        
        result = transcriber.transcribe_audio("audio.mp3", language="en")
        
        # Verify language parameter was passed
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]['language'] == "en"
    
    @patch('core.audio.OpenAI')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_transcribe_audio_handles_empty_response(self, mock_file, mock_getsize, mock_exists, mock_openai_class, transcriber):
        """Test handling of empty transcription response."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024
        
        mock_response = Mock()
        mock_response.text = ""  # Empty response
        
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        transcriber.client = mock_client
        
        with pytest.raises(ValueError, match="Transcription returned empty text"):
            transcriber.transcribe_audio("audio.mp3")
    
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_transcribe_audio_supports_all_formats(self, mock_getsize, mock_exists, transcriber):
        """Test that all supported formats are accepted."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024
        
        supported_formats = ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4', '.mpeg', '.mpga']
        
        for ext in supported_formats:
            filename = f"test{ext}"
            # Should not raise ValueError for format
            try:
                with patch('builtins.open', mock_open(read_data=b'data')):
                    with patch.object(transcriber.client.audio.transcriptions, 'create') as mock_create:
                        mock_response = Mock()
                        mock_response.text = "Transcribed"
                        mock_create.return_value = mock_response
                        transcriber.transcribe_audio(filename)
            except Exception as e:
                if "Unsupported audio format" in str(e):
                    pytest.fail(f"Format {ext} should be supported")
    
    def test_validate_audio_file_accepts_valid_file(self, tmp_path):
        """Test validation passes for valid audio file."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b'fake audio data' * 1000)  # Create small file
        
        is_valid, message = AudioTranscriber.validate_audio_file(str(audio_file))
        assert is_valid is True
        assert message == ""
    
    def test_validate_audio_file_rejects_missing_file(self):
        """Test validation fails for missing file."""
        is_valid, message = AudioTranscriber.validate_audio_file("nonexistent.mp3")
        assert is_valid is False
        assert "not exist" in message.lower()
    
    def test_validate_audio_file_rejects_unsupported_format(self, tmp_path):
        """Test validation fails for unsupported format."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("not audio")
        
        is_valid, message = AudioTranscriber.validate_audio_file(str(text_file))
        assert is_valid is False
        assert "unsupported" in message.lower()
    
    def test_validate_audio_file_rejects_oversized_file(self, tmp_path):
        """Test validation fails for file over configured limit."""
        # Create file larger than 200MB Flask upload limit
        large_file = tmp_path / "large.mp3"
        large_file.write_bytes(b'x' * (201 * 1024 * 1024))  # 201MB (over 200MB limit)
        
        is_valid, message = AudioTranscriber.validate_audio_file(str(large_file), max_size_mb=200)
        assert is_valid is False
        assert "too large" in message.lower()
    
    def test_validate_audio_file_rejects_empty_file(self, tmp_path):
        """Test validation fails for empty file."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.write_bytes(b'')
        
        is_valid, message = AudioTranscriber.validate_audio_file(str(empty_file))
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_audio_file_with_custom_max_size(self, tmp_path):
        """Test validation with custom max size."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b'x' * (15 * 1024 * 1024))  # 15MB
        
        # Should pass with 25MB limit
        is_valid, _ = AudioTranscriber.validate_audio_file(str(audio_file), max_size_mb=25)
        assert is_valid is True
        
        # Should fail with 10MB limit
        is_valid, message = AudioTranscriber.validate_audio_file(str(audio_file), max_size_mb=10)
        assert is_valid is False
        assert "too large" in message.lower()
    
    def test_validate_audio_file_with_custom_extensions(self, tmp_path):
        """Test validation with custom allowed extensions."""
        audio_file = tmp_path / "test.ogg"
        audio_file.write_bytes(b'fake audio')
        
        # Should pass with ogg in allowed set
        is_valid, _ = AudioTranscriber.validate_audio_file(
            str(audio_file),
            allowed_extensions={'.ogg', '.mp3'}
        )
        assert is_valid is True
        
        # Should fail with ogg not in allowed set
        is_valid, message = AudioTranscriber.validate_audio_file(
            str(audio_file),
            allowed_extensions={'.mp3', '.wav'}
        )
        assert is_valid is False
        assert "unsupported" in message.lower()
    
    def test_validate_audio_file_case_insensitive_extension(self, tmp_path):
        """Test that file extension check is case-insensitive."""
        audio_file = tmp_path / "test.MP3"  # Uppercase extension
        audio_file.write_bytes(b'fake audio')
        
        is_valid, message = AudioTranscriber.validate_audio_file(str(audio_file))
        assert is_valid is True
