"""
Audio transcription using OpenAI Whisper API.

Handles audio file upload and transcription to text, including chunking for large files.
"""
from typing import Optional, List, Callable
import os
from pathlib import Path
import math
import subprocess

from openai import OpenAI
from openai import OpenAIError

# pydub is imported only when needed for chunking (lazy import)
# This avoids Python 3.13 audioop compatibility issues when not using chunking


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
        language: Optional[str] = None,
        chunk_size_mb: int = 20,
        progress_callback: Optional[Callable[[dict], None]] = None
    ) -> str:
        """
        Transcribe audio file to text, with automatic chunking for large files.
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            chunk_size_mb: Target chunk size in MB for splitting large files
            progress_callback: Optional callback function(dict) called after each chunk
                             dict contains: {'chunk': #, 'total_chunks': #, 'duration_sec': #}
            
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
        
        # Check file size
        file_size = os.path.getsize(audio_file_path)
        file_size_mb = file_size / (1024 * 1024)
        chunk_threshold_mb = chunk_size_mb
        
        print(f"[AUDIO] File size: {file_size_mb:.1f}MB")
        
        # Use chunking for large files — use ffmpeg directly (memory-efficient: no full RAM load)
        if file_size_mb > chunk_threshold_mb:
            print(f"[AUDIO] File exceeds {chunk_threshold_mb}MB, using ffmpeg chunking approach")
            return self._transcribe_with_ffmpeg_chunking(audio_file_path, language, chunk_size_mb, progress_callback)
        
        # Standard single-file transcription for smaller files
        print(f"[AUDIO] File under {chunk_threshold_mb}MB, using standard transcription")
        return self._transcribe_single_file(audio_file_path, language)
    
    def _transcribe_single_file(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> str:
        """
        Transcribe a single audio file using Whisper API.
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code
            
        Returns:
            Transcribed text
        """
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
            
        except ValueError:
            # Re-raise ValueError as-is (for empty transcript validation)
            raise
        except OpenAIError as e:
            raise OpenAIError(f"Whisper API error: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error during transcription: {e}")
    
    def _transcribe_with_chunking(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        chunk_size_mb: int = 20,
        progress_callback: Optional[Callable[[dict], None]] = None
    ) -> str:
        """
        Transcribe large audio file by splitting into chunks.
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code
            chunk_size_mb: Target chunk size in MB
            
        Returns:
            Combined transcribed text from all chunks
        """
        # Lazy import pydub only when needed for chunking
        try:
            from pydub import AudioSegment
        except ImportError:
            print("[AUDIO] pydub not available; falling back to ffmpeg chunking")
            return self._transcribe_with_ffmpeg_chunking(audio_file_path, language, chunk_size_mb, progress_callback)
        
        print(f"[AUDIO] Loading audio file for chunking...")
        
        # Load audio file with pydub (requires ffprobe; catch failure and fall back)
        file_ext = Path(audio_file_path).suffix.lower().lstrip('.')
        try:
            audio = AudioSegment.from_file(audio_file_path, format=file_ext)
        except Exception as e:
            print(f"[AUDIO] pydub failed ({e}); falling back to ffmpeg chunking")
            return self._transcribe_with_ffmpeg_chunking(audio_file_path, language, chunk_size_mb, progress_callback)
        
        # Calculate chunk duration
        audio_duration_ms = len(audio)
        audio_duration_min = audio_duration_ms / 60000
        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        
        # Calculate how many chunks we need
        num_chunks = math.ceil(file_size_mb / chunk_size_mb)
        chunk_duration_ms = audio_duration_ms // num_chunks
        
        print(f"[AUDIO] Audio duration: {audio_duration_min:.1f} minutes")
        print(f"[AUDIO] Splitting into {num_chunks} chunks of ~{chunk_duration_ms/60000:.1f} minutes each")
        
        # Create temp directory for chunks
        temp_dir = Path(audio_file_path).parent / f"chunks_{Path(audio_file_path).stem}"
        temp_dir.mkdir(exist_ok=True)
        
        transcripts = []
        chunk_files = []
        
        try:
            # Split and transcribe chunks
            for i in range(num_chunks):
                start_ms = i * chunk_duration_ms
                end_ms = min((i + 1) * chunk_duration_ms, audio_duration_ms)
                
                print(f"[AUDIO] Processing chunk {i+1}/{num_chunks} ({start_ms/60000:.1f}-{end_ms/60000:.1f} min)...")
                
                # Extract chunk
                chunk = audio[start_ms:end_ms]
                
                # Save chunk
                chunk_path = temp_dir / f"chunk_{i:03d}.mp3"
                chunk.export(chunk_path, format="mp3")
                chunk_files.append(chunk_path)
                
                # Transcribe chunk
                print(f"[AUDIO] Transcribing chunk {i+1}/{num_chunks}...")
                chunk_transcript = self._transcribe_single_file(str(chunk_path), language)
                transcripts.append(chunk_transcript)
                
                print(f"[AUDIO] ✓ Chunk {i+1}/{num_chunks} completed ({len(chunk_transcript)} chars)")
                
                # Call progress callback
                if progress_callback:
                    progress_callback({
                        'chunk': i + 1,
                        'total_chunks': num_chunks,
                        'duration_sec': (end_ms - start_ms) / 1000
                    })
            
            # Combine transcripts
            print(f"[AUDIO] Combining {len(transcripts)} transcripts...")
            combined_transcript = "\n\n[Continuing...]\n\n".join(transcripts)
            
            print(f"[AUDIO] ✓ Chunking complete. Total transcript: {len(combined_transcript)} characters")
            return combined_transcript
            
        finally:
            # Clean up chunk files
            print(f"[AUDIO] Cleaning up temporary chunk files...")
            for chunk_file in chunk_files:
                try:
                    if chunk_file.exists():
                        chunk_file.unlink()
                except Exception as e:
                    print(f"[AUDIO] Warning: Could not delete {chunk_file}: {e}")
            
            # Remove temp directory
            try:
                if temp_dir.exists():
                    temp_dir.rmdir()
            except Exception as e:
                print(f"[AUDIO] Warning: Could not remove temp directory {temp_dir}: {e}")

    def _transcribe_with_ffmpeg_chunking(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        chunk_size_mb: int = 20,
        progress_callback: Optional[Callable[[dict], None]] = None
    ) -> str:
        """
        Transcribe large audio file by splitting into chunks using ffmpeg.
        """
        duration_sec = self._get_audio_duration_seconds(audio_file_path)
        if duration_sec <= 0:
            raise ValueError("Could not determine audio duration for chunking")

        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        num_chunks = max(1, math.ceil(file_size_mb / chunk_size_mb))
        chunk_duration_sec = max(1, math.ceil(duration_sec / num_chunks))

        print(f"[AUDIO] Audio duration: {duration_sec/60:.1f} minutes")
        print(f"[AUDIO] Splitting into {num_chunks} chunks of ~{chunk_duration_sec/60:.1f} minutes each")

        temp_dir = Path(audio_file_path).parent / f"chunks_{Path(audio_file_path).stem}"
        temp_dir.mkdir(exist_ok=True)

        output_pattern = temp_dir / "chunk_%03d.mp3"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            audio_file_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-f",
            "segment",
            "-segment_time",
            str(chunk_duration_sec),
            "-reset_timestamps",
            "1",
            str(output_pattern)
        ]

        print("[AUDIO] Running ffmpeg segmenter...")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            raise RuntimeError(f"ffmpeg chunking failed: {stderr}") from e

        chunk_files = sorted(temp_dir.glob("chunk_*.mp3"))
        if not chunk_files:
            raise RuntimeError("ffmpeg chunking produced no output files")

        transcripts = []
        try:
            for i, chunk_path in enumerate(chunk_files, start=1):
                print(f"[AUDIO] Transcribing chunk {i}/{len(chunk_files)}...")
                chunk_transcript = self._transcribe_single_file(str(chunk_path), language)
                transcripts.append(chunk_transcript)
                print(f"[AUDIO] ✓ Chunk {i}/{len(chunk_files)} completed ({len(chunk_transcript)} chars)")
                
                # Call progress callback
                if progress_callback:
                    print(f"[AUDIO] Calling progress_callback with chunk {i}/{len(chunk_files)}")
                    progress_callback({
                        'chunk': i,
                        'total_chunks': len(chunk_files),
                        'duration_sec': chunk_duration_sec
                    })
                else:
                    print(f"[AUDIO] No progress_callback provided")

            print(f"[AUDIO] Combining {len(transcripts)} transcripts...")
            combined_transcript = "\n\n[Continuing...]\n\n".join(transcripts)
            print(f"[AUDIO] ✓ Chunking complete. Total transcript: {len(combined_transcript)} characters")
            return combined_transcript
        finally:
            print(f"[AUDIO] Cleaning up temporary chunk files...")
            for chunk_file in chunk_files:
                try:
                    if chunk_file.exists():
                        chunk_file.unlink()
                except Exception as e:
                    print(f"[AUDIO] Warning: Could not delete {chunk_file}: {e}")

            try:
                if temp_dir.exists():
                    temp_dir.rmdir()
            except Exception as e:
                print(f"[AUDIO] Warning: Could not remove temp directory {temp_dir}: {e}")

    @staticmethod
    def _get_audio_duration_seconds(audio_file_path: str) -> float:
        """
        Get audio duration in seconds using ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_file_path
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            raise RuntimeError(f"ffprobe failed: {stderr}") from e

        try:
            return float(result.stdout.strip())
        except ValueError as e:
            raise RuntimeError("ffprobe returned invalid duration") from e
    
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
