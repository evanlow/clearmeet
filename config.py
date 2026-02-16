"""
Configuration module for ClearMeet application.

Handles environment variables and application settings.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class with all settings."""
    
    # Flask Configuration
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG: bool = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING: bool = False
    
    # Session Configuration
    SESSION_TYPE: str = 'filesystem'
    PERMANENT_SESSION_LIFETIME: int = int(os.getenv('PERMANENT_SESSION_LIFETIME', '3600'))
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH: int = int(os.getenv('MAX_CONTENT_LENGTH', str(200 * 1024 * 1024)))  # 200MB (supports chunking)
    UPLOAD_FOLDER: str = os.getenv('UPLOAD_FOLDER', 'temp_uploads')
    _raw_audio_exts = os.getenv('ALLOWED_AUDIO_EXTENSIONS', 'mp3,wav,m4a,ogg')
    ALLOWED_AUDIO_EXTENSIONS: set = {
        ext if ext.startswith('.') else f".{ext}"
        for ext in [e.strip().lower() for e in _raw_audio_exts.split(',')]
        if ext
    }
    
    # Audio Processing Configuration
    CHUNK_SIZE_MB: int = int(os.getenv('CHUNK_SIZE_MB', '20'))  # Target chunk size for large files
    WHISPER_API_LIMIT_MB: int = 25  # OpenAI Whisper API file size limit
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    OPENAI_TEMPERATURE: float = float(os.getenv('OPENAI_TEMPERATURE', '0.3'))
    WHISPER_MODEL: str = os.getenv('WHISPER_MODEL', 'whisper-1')
    
    @staticmethod
    def validate_config() -> tuple[bool, str]:
        """
        Validate required configuration values.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not Config.OPENAI_API_KEY:
            return False, "OPENAI_API_KEY environment variable is required"
        
        if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            if not Config.DEBUG:
                return False, "SECRET_KEY must be set in production"
        
        return True, ""


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


class TestConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    OPENAI_API_KEY = 'test-api-key'
    SECRET_KEY = 'test-secret-key'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}


def get_config(env: Optional[str] = None) -> type[Config]:
    """
    Get configuration class based on environment.
    
    Args:
        env: Environment name (development, production, testing)
        
    Returns:
        Configuration class
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    return config.get(env, config['default'])
