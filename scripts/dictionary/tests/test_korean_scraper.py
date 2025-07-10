import os
import sys
import tempfile
import pytest
import yaml
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError
from rich.console import Console
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from korean import (
    KoreanEntry,
    upsert_korean_entry,
    parse_korean_entry_from_yaml_item,
    parse_korean_yml,
    main
)


class TestKoreanEntry:
    """Test cases for the KoreanEntry Pydantic model."""
    
    def test_korean_entry_valid_minimal(self):
        """Test creating a KoreanEntry with minimal required fields."""
        entry = KoreanEntry(word="안녕")
        assert entry.word == "안녕"
        assert entry.romaja is None
        assert entry.pos is None
        assert entry.defs is None
        assert entry.conj is None
        assert entry.notes is None
        assert entry.syns is None
        assert entry.tags is None
    
    def test_korean_entry_valid_full(self):
        """Test creating a KoreanEntry with all fields populated."""
        entry = KoreanEntry(
            word="안녕",
            romaja="annyeong",
            pos="n",
            defs=["hello", "goodbye"],
            conj=["안녕하다"],
            notes=["informal greeting"],
            syns=["인사"],
            tags=["greeting", "common"]
        )
        assert entry.word == "안녕"
        assert entry.romaja == "annyeong"
        assert entry.pos == "n"
        assert entry.defs == ["hello", "goodbye"]
        assert entry.conj == ["안녕하다"]
        assert entry.notes == ["informal greeting"]
        assert entry.syns == ["인사"]
        assert entry.tags == ["greeting", "common"]
    
    def test_korean_entry_invalid_missing_word(self):
        """Test that KoreanEntry raises ValidationError when word is missing."""
        with pytest.raises(ValidationError):
            KoreanEntry()
    
    def test_korean_entry_invalid_word_type(self):
        """Test that KoreanEntry raises ValidationError when word is not a string."""
        with pytest.raises(ValidationError):
            KoreanEntry(word=123)
    
    def test_korean_entry_invalid_list_field_type(self):
        """Test that KoreanEntry raises ValidationError when list fields have wrong types."""
        with pytest.raises(ValidationError):
            KoreanEntry(word="test", defs="not a list")
    
    def test_korean_entry_model_dump(self):
        """Test that model_dump works correctly and excludes None values."""
        entry = KoreanEntry(word="test", romaja="test", defs=["definition"])
        dumped = entry.model_dump(exclude_none=True)
        expected = {
            "word": "test",
            "romaja": "test",
            "defs": ["definition"]
        }
        assert dumped == expected


class TestUpsertKoreanEntry:
    """Test cases for the upsert_korean_entry function."""
    
    def test_upsert_korean_entry_success(self):
        """Test successful upsert of a Korean entry."""
        # Mock Supabase client
        mock_supabase = Mock()
        mock_table = Mock()
        mock_upsert = Mock()
        mock_response = Mock()
        mock_response.data = [{"word": "test", "romaja": "test"}]
        
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = mock_response
        
        # Create test entry
        entry = KoreanEntry(word="test", romaja="test")
        
        # Test upsert
        result = upsert_korean_entry(mock_supabase, entry)
        
        # Assertions
        assert result is True
        mock_supabase.table.assert_called_once_with("korean_entries")
        mock_table.upsert.assert_called_once_with({"word": "test", "romaja": "test"})
        mock_upsert.execute.assert_called_once()
    
    def test_upsert_korean_entry_success_empty_data(self):
        """Test successful upsert when Supabase returns empty data."""
        # Mock Supabase client
        mock_supabase = Mock()
        mock_table = Mock()
        mock_upsert = Mock()
        mock_response = Mock()
        mock_response.data = []  # Empty data but still success
        
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = mock_response
        
        # Create test entry
        entry = KoreanEntry(word="test")
        
        # Test upsert
        result = upsert_korean_entry(mock_supabase, entry)
        
        # Should still return True for empty data
        assert result is True
    
    def test_upsert_korean_entry_exception(self):
        """Test upsert when Supabase throws an exception."""
        # Mock Supabase client that raises an exception
        mock_supabase = Mock()
        mock_supabase.table.side_effect = Exception("Database error")
        
        # Create test entry
        entry = KoreanEntry(word="test")
        
        # Test upsert raises exception
        with pytest.raises(Exception, match="Database error"):
            upsert_korean_entry(mock_supabase, entry)


class TestParseKoreanEntryFromYamlItem:
    """Test cases for the parse_korean_entry_from_yaml_item function."""
    
    def test_parse_valid_minimal_entry(self):
        """Test parsing a minimal valid YAML item."""
        item = {"word": "안녕"}
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        assert result.word == "안녕"
        assert result.romaja is None
    
    def test_parse_valid_full_entry(self):
        """Test parsing a complete valid YAML item."""
        item = {
            "word": "악영향",
            "romaja": "agyeonghyang",
            "pos": "n",
            "defs": [{"def": "bad influence; adverse effect"}],
            "tags": ["common"]
        }
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        assert result.word == "악영향"
        assert result.romaja == "agyeonghyang"
        assert result.pos == "n"
        assert result.defs == ["bad influence; adverse effect"]
        assert result.tags == ["common"]
    
    def test_parse_boolean_romaja_conversion(self):
        """Test that boolean romaja values are converted to strings."""
        item = {
            "word": "test",
            "romaja": True  # Boolean value that should be converted
        }
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        assert result.romaja == "True"
    
    def test_parse_string_to_list_normalization(self):
        """Test that string fields are normalized to lists when needed."""
        item = {
            "word": "test",
            "notes": "single note",  # String that should become list
            "defs": "single definition",
            "tags": "single tag"
        }
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        assert result.notes == ["single note"]
        assert result.defs == ["single definition"]
        assert result.tags == ["single tag"]
    
    def test_parse_defs_dict_extraction(self):
        """Test extraction of 'def' strings from definition dictionaries."""
        item = {
            "word": "test",
            "defs": [
                {"def": "definition 1"},
                {"def": "definition 2"},
                "string definition"  # Mix of dict and string
            ]
        }
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        assert result.defs == ["definition 1", "definition 2", "string definition"]
    
    def test_parse_defs_dict_missing_def_key(self):
        """Test handling of definition dictionaries without 'def' key."""
        item = {
            "word": "test",
            "defs": [
                {"def": "good definition"},
                {"example": "no def key"}  # Missing 'def' key
            ]
        }
        result = parse_korean_entry_from_yaml_item(item, 1)
        
        assert result is not None
        # The actual behavior appears to skip items without 'def' key
        assert result.defs == ["good definition"]
    
    def test_parse_validation_error(self):
        """Test parsing with validation error."""
        item = {}  # Missing required 'word' field
        
        with patch('korean.console') as mock_console:
            result = parse_korean_entry_from_yaml_item(item, 1)
            
            assert result is None
            mock_console.log.assert_called_once()
            # Check that the log call includes validation error info
            call_args = mock_console.log.call_args[0][0]
            assert "Parsing Failed" in call_args
            assert "validation error" in call_args
    
    def test_parse_unexpected_exception(self):
        """Test parsing with unexpected exception."""
        item = {"word": "test"}
        
        with patch('korean.KoreanEntry') as mock_korean_entry:
            mock_korean_entry.side_effect = Exception("Unexpected error")
            
            with patch('korean.console') as mock_console:
                result = parse_korean_entry_from_yaml_item(item, 1)
                
                assert result is None
                mock_console.log.assert_called_once()
                call_args = mock_console.log.call_args[0][0]
                assert "Parsing Failed" in call_args
                assert "unexpected error" in call_args


class TestParseKoreanYml:
    """Test cases for the parse_korean_yml function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_yaml_data = [
            {
                "word": "악영향",
                "romaja": "agyeonghyang",
                "pos": "n",
                "defs": [{"def": "bad influence; adverse effect"}]
            },
            {
                "word": "악티늄",
                "romaja": "aktinyum",
                "pos": "n",
                "defs": [{"def": "actinium"}]
            }
        ]
    
    def test_parse_korean_yml_file_not_found(self):
        """Test behavior when YAML file doesn't exist."""
        with patch('korean.console') as mock_console:
            parse_korean_yml(upsert=False, interval=1, file_path="nonexistent.yml")
            
            mock_console.log.assert_called()
            # Should log an error about file not found
            logged_messages = [call[0][0] for call in mock_console.log.call_args_list]
            assert any("not found" in msg for msg in logged_messages)
    
    def test_parse_korean_yml_yaml_error(self):
        """Test behavior when YAML parsing fails."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML
            temp_file = f.name
        
        try:
            with patch('korean.console') as mock_console:
                parse_korean_yml(upsert=False, interval=1, file_path=temp_file)
                
                mock_console.log.assert_called()
                logged_messages = [call[0][0] for call in mock_console.log.call_args_list]
                assert any("Error parsing YAML" in msg for msg in logged_messages)
        finally:
            # Use try-except to handle file deletion on Windows
            try:
                os.unlink(temp_file)
            except (FileNotFoundError, PermissionError):
                pass
    
    def test_parse_korean_yml_invalid_yaml_structure(self):
        """Test behavior when YAML is not a list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({"not": "a list"}, f)  # Valid YAML but not a list
            temp_file = f.name
        
        try:
            with patch('korean.console') as mock_console:
                parse_korean_yml(upsert=False, interval=1, file_path=temp_file)
                
                mock_console.log.assert_called()
                logged_messages = [call[0][0] for call in mock_console.log.call_args_list]
                assert any("must be a list" in msg for msg in logged_messages)
        finally:
            # Use try-except to handle file deletion on Windows
            try:
                os.unlink(temp_file)
            except (FileNotFoundError, PermissionError):
                pass
    
    @patch('korean.Confirm.ask')
    def test_parse_korean_yml_user_cancellation(self, mock_confirm):
        """Test behavior when user cancels after preview."""
        mock_confirm.return_value = False  # User says no
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(self.test_yaml_data, f)
            temp_file = f.name
        
        try:
            with patch('korean.console') as mock_console:
                with pytest.raises(SystemExit):
                    parse_korean_yml(upsert=False, interval=1, file_path=temp_file)
                
                # Should log cancellation message
                logged_messages = [call[0][0] for call in mock_console.log.call_args_list]
                assert any("cancelled by user" in msg for msg in logged_messages)
        finally:
            try:
                os.unlink(temp_file)
            except (FileNotFoundError, PermissionError):
                pass
    
def test_parse_korean_yml_with_upsert_success():
    test_yaml_data = [
        {"word": "사랑", "romaja": "sarang", "defs": ["love"]},
        {"word": "테스트", "romaja": "teseuteu", "defs": ["test"]},
    ]

    buffer = StringIO()
    console = Console(file=buffer)

    with patch('korean.console', console), \
         patch('korean.Confirm.ask') as mock_confirm, \
         patch('korean.setup_supabase_client') as mock_supabase_setup, \
         patch('korean.upsert_korean_entry', return_value=True) as mock_upsert:

        mock_confirm.return_value = True
        mock_supabase_setup.return_value = Mock()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False, encoding='utf-8') as f:
            yaml.dump(test_yaml_data, f, allow_unicode=True)
            temp_file = f.name

        try:
            parse_korean_yml(upsert=True, interval=1, file_path=temp_file)

            assert mock_upsert.call_count == len(test_yaml_data)

            output = buffer.getvalue()
            assert "Parsing" in output  # or any other expected message

        finally:
            try:
                os.unlink(temp_file)
            except (FileNotFoundError, PermissionError):
                pass
@patch('korean.log_config_loaded')
@patch('korean.parse_korean_yml')
@patch('korean.download_file')
@patch('korean.KoreanScraper')
def test_main_success_flow(mock_scraper, mock_download, mock_parse, mock_log_config):
    # mock_scraper is the mock for KoreanScraper class
    # We want to mock its model_dump classmethod
    mock_scraper.model_dump = MagicMock(return_value={
        "source": "http://example.com/test.yml",
        "protocol": "http",
        "file_type": "yml",
        "zip_type": "none",
        "file_name": "test.yml",
        "interval": 1,
        "upsert": False
    })

    mock_download.return_value = "/tmp/test.yml"

    # Call the main function under test
    main()

    mock_log_config.assert_called_once()
    mock_download.assert_called_once_with("http://example.com/test.yml", "test.yml")
    mock_parse.assert_called_once_with(False, 1, "/tmp/test.yml")


# Integration test with actual YAML data
class TestIntegration:
    """Integration tests using actual YAML data structure."""
    
    def test_parse_actual_yaml_structure(self):
        """Test parsing with the actual YAML structure from the example."""
        yaml_data = [
            {
                "word": "악영향",
                "romaja": "agyeonghyang",
                "pos": "n",
                "defs": [{"def": "bad influence; adverse effect"}]
            },
            {
                "word": "안",
                "romaja": "an",
                "pos": "adv",
                "defs": [{"def": "not", "examples": [
                    {
                        "example": "안 먹어?",
                        "transliteration": "An meogeo?",
                        "translation": "Won't [you] eat?"
                    }
                ]}],
                "tags": ["topik1"]
            }
        ]
        
        # Test parsing each entry
        for i, item in enumerate(yaml_data):
            result = parse_korean_entry_from_yaml_item(item, i + 1)
            assert result is not None
            assert result.word == item["word"]
            assert result.romaja == item["romaja"]
            assert result.pos == item["pos"]
            
            # Check that definitions are extracted correctly
            if "defs" in item:
                expected_defs = []
                for def_item in item["defs"]:
                    if isinstance(def_item, dict) and "def" in def_item:
                        expected_defs.append(def_item["def"])
                    elif isinstance(def_item, str):
                        expected_defs.append(def_item)
                assert result.defs == expected_defs
            
            # Check tags if present
            if "tags" in item:
                assert result.tags == item["tags"]


if __name__ == "__main__":
    pytest.main([__file__])