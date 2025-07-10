import sys
import os
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

# Ensure python can import chinese.py from parent folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chinese import (
    ChineseEntry,
    parse_chinese_entry,
    upsert_chinese_entry,
    parse_chinese_txt,
)


# --------------------------
# Unit tests for parse_chinese_entry
# --------------------------

def test_valid_chinese_entry():
    line = "憂鬱 忧郁 [you1 yu4] /melancholy/dejected/depressed/"
    entry = parse_chinese_entry(line)
    assert isinstance(entry, ChineseEntry)
    assert entry.traditional == "憂鬱"
    assert entry.simplified == "忧郁"
    assert entry.pronunciation == "you1 yu4"
    assert entry.definitions == ["melancholy", "dejected", "depressed"]
    print("chinese entry is valid! :)")


def test_invalid_format_entry_returns_none():
    line = "this is invalid format"
    assert parse_chinese_entry(line) is None


def test_entry_with_missing_fields_returns_none():
    line = "憂鬱 忧郁 /melancholy/"
    assert parse_chinese_entry(line) is None


# --------------------------
# Unit test for upsert_chinese_entry
# --------------------------

def test_upsert_chinese_entry_success():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = [{"id": 123}]

    entry = ChineseEntry(
        traditional="憂鬱",
        simplified="忧郁",
        pronunciation="you1 yu4",
        definitions=["melancholy"]
    )

    result = upsert_chinese_entry(mock_supabase, entry)
    assert result == {"id": 123}


def test_upsert_chinese_entry_failure_returns_empty_dict():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = None

    entry = ChineseEntry(
        traditional="憂鬱",
        simplified="忧郁",
        pronunciation="you1 yu4",
        definitions=["melancholy"]
    )

    result = upsert_chinese_entry(mock_supabase, entry)
    assert result == {}


# --------------------------
# Working test for parse_chinese_txt
# --------------------------

@patch("chinese.os.path.exists", return_value=True)
@patch("chinese.setup_supabase_client")
@patch("chinese.upsert_chinese_entry", return_value={"id": 1})
@patch("chinese.Confirm.ask", return_value=True)
@patch("chinese.os.remove")
def test_parse_chinese_txt_with_upsert_working(
    mock_remove, mock_confirm, mock_upsert, mock_setup, mock_exists
):
    """
    This test properly mocks all file operations to ensure the parsing logic works.
    """
    mock_setup.return_value = MagicMock()

    # File content that should be parsed
    file_content = "憂鬱 忧郁 [you1 yu4] /melancholy/dejected/depressed/\n"
    
    # Create a proper StringIO-based mock that handles multiple reads correctly
    class ResetableStringIO(StringIO):
        def __init__(self, content):
            super().__init__(content)
            self.content = content
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def __iter__(self):
            # Reset position before iterating
            self.seek(0)
            return self
            
        def __next__(self):
            line = self.readline()
            if line:
                return line
            raise StopIteration
    
    # Mock the open function to return our resetable StringIO
    def mock_open_func(*args, **kwargs):
        return ResetableStringIO(file_content)
    
    with patch("chinese.open", side_effect=mock_open_func):
        parse_chinese_txt(upsert=True, interval=1, file_path="dummy.txt")

    print(f"upsert_chinese_entry call count: {mock_upsert.call_count}")

    # Verify the function was called as expected
    mock_confirm.assert_called_once()
    mock_upsert.assert_called_once()
    
    # Verify the correct entry was passed to upsert
    call_args = mock_upsert.call_args
    assert call_args is not None
    entry = call_args[0][1]  # Second argument (first is client)
    assert isinstance(entry, ChineseEntry)
    assert entry.traditional == "憂鬱"
    assert entry.simplified == "忧郁"
    assert entry.pronunciation == "you1 yu4"
    assert entry.definitions == ["melancholy", "dejected", "depressed"]
    
    mock_remove.assert_called_once()


# Alternative approach using a more traditional mock
@patch("chinese.os.path.exists", return_value=True)
@patch("chinese.setup_supabase_client")
@patch("chinese.upsert_chinese_entry", return_value={"id": 1})
@patch("chinese.Confirm.ask", return_value=True)
@patch("chinese.os.remove")
def test_parse_chinese_txt_alternative_approach(
    mock_remove, mock_confirm, mock_upsert, mock_setup, mock_exists
):
    """
    Alternative approach using mock_open with proper configuration.
    """
    mock_setup.return_value = MagicMock()

    # File content
    file_content = "憂鬱 忧郁 [you1 yu4] /melancholy/dejected/depressed/\n"
    
    # Create a mock that can be read multiple times
    mock_file = mock_open(read_data=file_content)
    
    # Configure the mock to handle multiple reads
    mock_file.return_value.__iter__ = lambda self: iter(file_content.splitlines(True))
    
    with patch("chinese.open", mock_file):
        parse_chinese_txt(upsert=True, interval=1, file_path="dummy.txt")

    print(f"upsert_chinese_entry call count: {mock_upsert.call_count}")

    mock_confirm.assert_called_once()
    mock_upsert.assert_called_once()
    mock_remove.assert_called_once()


# Test without upserting to isolate parsing logic
@patch("chinese.os.path.exists", return_value=True)
@patch("chinese.Confirm.ask", return_value=True)
@patch("chinese.os.remove")
def test_parse_chinese_txt_without_upsert(mock_remove, mock_confirm, mock_exists):
    """
    Test parsing without upserting to ensure the parsing logic itself works.
    """
    file_content = "憂鬱 忧郁 [you1 yu4] /melancholy/dejected/depressed/\n"
    
    class ResetableStringIO(StringIO):
        def __init__(self, content):
            super().__init__(content)
            self.content = content
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def __iter__(self):
            self.seek(0)
            return self
            
        def __next__(self):
            line = self.readline()
            if line:
                return line
            raise StopIteration
    
    def mock_open_func(*args, **kwargs):
        return ResetableStringIO(file_content)
    
    with patch("chinese.open", side_effect=mock_open_func):
        # This should complete without errors and show parsing stats
        parse_chinese_txt(upsert=False, interval=1, file_path="dummy.txt")

    mock_confirm.assert_called_once()
    mock_remove.assert_called_once()


# Test with multiple lines to ensure interval logic works
@patch("chinese.os.path.exists", return_value=True)
@patch("chinese.setup_supabase_client")
@patch("chinese.upsert_chinese_entry", return_value={"id": 1})
@patch("chinese.Confirm.ask", return_value=True)
@patch("chinese.os.remove")
def test_parse_chinese_txt_with_interval(
    mock_remove, mock_confirm, mock_upsert, mock_setup, mock_exists
):
    """
    Test with multiple lines and interval=2 to ensure interval logic works correctly.
    """
    mock_setup.return_value = MagicMock()

    # Multiple lines of content
    file_content = """憂鬱 忧郁 [you1 yu4] /melancholy/dejected/depressed/
快樂 快乐 [kuai4 le4] /happy/cheerful/
悲傷 悲伤 [bei1 shang1] /sad/sorrowful/
興奮 兴奋 [xing4 fen4] /excited/thrilled/
"""
    
    class ResetableStringIO(StringIO):
        def __init__(self, content):
            super().__init__(content)
            self.content = content
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def __iter__(self):
            self.seek(0)
            return self
            
        def __next__(self):
            line = self.readline()
            if line:
                return line
            raise StopIteration
    
    def mock_open_func(*args, **kwargs):
        return ResetableStringIO(file_content)
    
    with patch("chinese.open", side_effect=mock_open_func):
        # With interval=2, should process lines 0, 2 (first and third lines)
        parse_chinese_txt(upsert=True, interval=2, file_path="dummy.txt")

    print(f"upsert_chinese_entry call count: {mock_upsert.call_count}")

    mock_confirm.assert_called_once()
    # Should be called twice (for lines 0 and 2)
    assert mock_upsert.call_count == 2
    mock_remove.assert_called_once()