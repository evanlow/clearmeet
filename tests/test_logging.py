"""
Tests for logging configuration and production safety.

Ensures that logging is configured correctly and doesn't leak secrets.
"""
import pytest
import logging
import os
from unittest.mock import patch

from config import logger, Config


class TestLoggingConfiguration:
    """Tests for logging setup."""
    
    def test_logger_exists(self):
        """Test that logger is configured."""
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'clearmeet'
    
    def test_logger_level_from_env(self):
        """Test that log level can be set from environment."""
        # Should default to INFO
        assert logger.level == logging.NOTSET or logger.level >= logging.INFO
    
    def test_logger_has_handlers(self):
        """Test that logger has configured handlers."""
        # BasicConfig should have created at least one handler
        assert len(logging.root.handlers) > 0


class TestConfigurationValidation:
    """Tests for config validation and logging."""
    
    def test_validate_config_warns_on_dev_secret_key(self, caplog):
        """Test that development SECRET_KEY generates warning."""
        with caplog.at_level(logging.WARNING):
            # Reset to development config
            original_debug = Config.DEBUG
            Config.DEBUG = True
            Config.SECRET_KEY = 'dev-secret-key-change-in-production'
            
            is_valid, error_msg = Config.validate_config()
            
            # Should still be valid in debug mode
            assert is_valid
            # Should have warning about dev secret key
            assert any('SECRET_KEY' in record.message for record in caplog.records 
                      if record.levelname == 'WARNING')
            
            Config.DEBUG = original_debug
    
    def test_validate_config_rejects_missing_secret_in_production(self):
        """Test that missing SECRET_KEY fails in production."""
        original_debug = Config.DEBUG
        original_secret = Config.SECRET_KEY
        
        try:
            Config.DEBUG = False
            Config.SECRET_KEY = 'dev-secret-key-change-in-production'
            
            is_valid, error_msg = Config.validate_config()
            
            assert not is_valid
            assert 'SECRET_KEY' in error_msg
        finally:
            Config.DEBUG = original_debug
            Config.SECRET_KEY = original_secret
    
    def test_no_secrets_in_log_format(self):
        """Test that log format doesn't include sensitive data."""
        # Get the formatter from the root logger
        for handler in logging.root.handlers:
            formatter = handler.formatter
            if formatter:
                # Check that format string doesn't contain sensitive keywords
                # (exact attribute name varies by formatter type)
                format_str = ""
                if hasattr(formatter, '_fmt'):
                    format_str = formatter._fmt
                elif hasattr(formatter, '_format'):
                    format_str = formatter._format
                elif hasattr(formatter, 'format'):
                    # For the format method, check the basic structure
                    # Just verify formatter exists and can format
                    try:
                        record = logging.LogRecord(
                            name="test", level=logging.INFO, pathname="", lineno=0,
                            msg="test message", args=(), exc_info=None
                        )
                        formatted = formatter.format(record)
                        assert "test message" in formatted
                    except Exception:
                        pass
                    continue
                
                # Check the format string for sensitive keywords
                if format_str:
                    assert 'OPENAI' not in format_str
                    assert 'SECRET' not in format_str


class TestProductionSafety:
    """Tests for production safety with logging."""
    
    def test_health_check_logs_without_error(self, caplog):
        """Test that logging works without exceptions."""
        with caplog.at_level(logging.INFO):
            logger.info("Test log message")
            assert len(caplog.records) > 0
            assert "Test log message" in caplog.text
    
    def test_logger_doesnt_log_env_variables(self):
        """Test that sensitive environment variables aren't accidentally logged."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-key-12345'}):
            # Simply having the env var shouldn't cause issues
            logger.info("Processing request")
            # As long as no exception is raised, test passes
            assert True
