import json
import csv
from pathlib import Path
import pytest
from zh_en_translator.engines.history import HistoryManager

@pytest.fixture
def history_file(tmp_path):
    return tmp_path / "history.json"

@pytest.fixture
def manager(history_file):
    return HistoryManager(history_file, max_items=3)

def test_add_entry(manager, history_file):
    manager.add_entry("Hello", "你好")
    history = manager.load_history()
    assert len(history) == 1
    assert history[0]["source"] == "Hello"
    assert history[0]["translation"] == "你好"
    assert "timestamp" in history[0]

def test_rotation(manager):
    manager.add_entry("1", "one")
    manager.add_entry("2", "two")
    manager.add_entry("3", "three")
    manager.add_entry("4", "four")
    
    history = manager.load_history()
    assert len(history) == 3
    assert history[0]["source"] == "4"
    assert history[2]["source"] == "2"

def test_clear_history(manager, history_file):
    manager.add_entry("Hello", "你好")
    assert history_file.exists()
    manager.clear_history()
    assert not history_file.exists()
    assert manager.load_history() == []

def test_export_to_csv(manager, tmp_path):
    manager.add_entry("Hello", "你好")
    export_path = tmp_path / "export.csv"
    success = manager.export_to_csv(export_path)
    assert success
    assert export_path.exists()
    
    with open(export_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["source"] == "Hello"
        assert rows[0]["translation"] == "你好"

def test_load_invalid_json(history_file):
    history_file.write_text("invalid json")
    manager = HistoryManager(history_file)
    assert manager.load_history() == []

def test_avoid_consecutive_duplicates(manager):
    manager.add_entry("Hello", "你好")
    manager.add_entry("Hello", "你好")
    assert len(manager.load_history()) == 1
