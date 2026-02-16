"""
Text parsing utilities for processing meeting transcripts.

Handles cleaning, formatting, and basic text analysis.
"""
from typing import Optional
import re


class TranscriptParser:
    """Parse and clean meeting transcripts."""
    
    @staticmethod
    def clean_transcript(text: str) -> str:
        """
        Clean raw transcript text.
        
        Args:
            text: Raw transcript text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common filler words if repeated excessively
        # (but keep natural speech patterns)
        text = re.sub(r'\b(um|uh|like)\b\s*(\1\s*)+', r'\1 ', text, flags=re.IGNORECASE)
        
        # Normalize line breaks
        text = text.strip()
        
        return text
    
    @staticmethod
    def estimate_duration(text: str, words_per_minute: int = 150) -> int:
        """
        Estimate meeting duration in minutes based on transcript length.
        
        Args:
            text: Transcript text
            words_per_minute: Average speaking rate
            
        Returns:
            Estimated duration in minutes
        """
        if not text:
            return 0
        
        words = len(text.split())
        duration = max(1, words // words_per_minute)
        
        return duration
    
    @staticmethod
    def extract_speakers(text: str) -> list[str]:
        """
        Extract speaker names from transcript if present.
        
        Looks for patterns like "John: " or "[Alice]" or "Speaker 1:"
        
        Args:
            text: Transcript text
            
        Returns:
            List of unique speaker names found
        """
        if not text:
            return []
        
        speakers = set()
        
        # Pattern 1: "Name:" at start of line or after period
        pattern1 = re.findall(r'(?:^|\. )([A-Z][a-z]+(?:\s[A-Z][a-z]+)?):', text)
        speakers.update(pattern1)
        
        # Pattern 2: "[Name]" or "(Name)"
        pattern2 = re.findall(r'[\[\(]([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)[\]\)]', text)
        speakers.update(pattern2)
        
        # Pattern 3: "Speaker N:"
        pattern3 = re.findall(r'(Speaker\s+\d+):', text)
        speakers.update(pattern3)
        
        return sorted(list(speakers))
    
    @staticmethod
    def validate_transcript(text: str, min_words: int = 50) -> tuple[bool, str]:
        """
        Validate that transcript meets minimum quality requirements.
        
        Args:
            text: Transcript text
            min_words: Minimum word count required
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Transcript is empty"
        
        words = text.split()
        if len(words) < min_words:
            return False, f"Transcript too short (minimum {min_words} words, got {len(words)})"
        
        # Check if it's mostly gibberish (very high punctuation ratio)
        if len(text) > 0:
            punct_ratio = sum(1 for c in text if c in '!@#$%^&*(){}[]') / len(text)
            if punct_ratio > 0.3:
                return False, "Transcript contains too many special characters"
        
        return True, ""
