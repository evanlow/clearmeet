"""
Audio transcription using OpenAI Whisper API.

Handles audio file upload and transcription to text.
"""
from typing import Optional
import os
from pathlib import Path

from openai import OpenAI
from openai import OpenAIError


class AudioTranscriber:
    """Transcribe audio files to text using Whisper API."""
    
    def __init__(self, api_key: str, model: str = "whisper-1"):
        """
        Initialize audio transcriber.
        
        Args:
            api_key: OpenAI API key
            model: Whisper model identifier
        """
        if not api_key:
            raise ValueError("API key is required")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            
        Returns:
            Transcribed text
            
        Raises:
            FileNotFoundError: If audio file doesn't exist
            ValueError: If file format not supported
            OpenAIError: If API call fails
        """
        # Validate file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        # Validate file extension
        allowed_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4', '.mpeg', '.mpga'}
        file_ext = Path(audio_file_path).suffix.lower()
        if file_ext not in allowed_extensions:
            raise ValueError(f"Unsupported audio format: {file_ext}")
        
        # Check file size (25MB limit for Whisper API)
        file_size = os.path.getsize(audio_file_path)
        max_size = 25 * 1024 * 1024  # 25MB
        if file_size > max_size:
            raise ValueError(f"Audio file too large ({file_size} bytes, max {max_size} bytes)")
        
        try:
            # Open and transcribe audio file
            with open(audio_file_path, 'rb') as audio_file:
                params = {
                    "model": self.model,
                    "file": audio_file,
                }
                
                if language:
                    params["language"] = language
                
                response = self.client.audio.transcriptions.create(**params)
            
            # Extract transcript text
            transcript = response.text
            
            if not transcript or not transcript.strip():
                raise ValueError("Transcription returned empty text")
            
            return transcript.strip()
            
        except OpenAIError as e:
            raise OpenAIError(f"Whisper API error: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error during transcription: {e}")
    
    @staticmethod
    def validate_audio_file(
        file_path: str,
        max_size_mb: int = 25,
        allowed_extensions: Optional[set] = None
    ) -> tuple[bool, str]:
        """
        Validate audio file before transcription.
        
        Args:
            file_path: Path to audio file
            max_size_mb: Maximum file size in MB
            allowed_extensions: Set of allowed extensions (with dot)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if allowed_extensions is None:
            allowed_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4', '.mpeg', '.mpga'}
        
        # Check file exists
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in allowed_extensions:
            return False, f"Unsupported format: {file_ext}"
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_bytes = max_size_mb * 1024 * 1024
        if file_size > max_bytes:
            return False, f"File too large ({file_size / 1024 / 1024:.1f}MB, max {max_size_mb}MB)"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, ""
