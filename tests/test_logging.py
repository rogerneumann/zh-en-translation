"""Unit tests for logging setup."""

import logging
from pathlib import Path
from zh_en_translator.app import setup_logging

def test_setup_logging(tmp_path, monkeypatch):
    """Test that setup_logging creates the log file and configures handlers."""
    # Redirect config path to tmp_path
    monkeypatch.setattr("zh_en_translator.config.get_config_path", lambda: tmp_path / "config.toml")
    
    # We need to clear handlers on the root logger before and after test
    # to avoid polluting other tests.
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    root_logger.handlers = []
    
    try:
        setup_logging()
        
        log_file = tmp_path / "logs" / "app.log"
        assert log_file.exists()
        
        # Verify that handlers were added
        assert len(root_logger.handlers) >= 1
        
        # Verify first log message
        content = log_file.read_text(encoding="utf-8")
        assert "Application Started" in content
        
    finally:
        # Restore old handlers
        for h in root_logger.handlers:
            h.close()
        root_logger.handlers = old_handlers
