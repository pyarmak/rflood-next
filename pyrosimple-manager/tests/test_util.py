import pytest
import os
from unittest.mock import patch, MagicMock, mock_open, call # For mocking

# Import the module/functions/classes to be tested
import util

# ===================================================================
# Tests for BTIH Class
# ===================================================================

def test_btih_valid_40_chars():
    """Test BTIH with a valid 40-character hash."""
    valid_hash = "a" * 40
    btih_obj = util.BTIH(valid_hash)
    assert str(btih_obj) == valid_hash
    assert repr(btih_obj) == f"BTIH('{valid_hash}')"

def test_btih_valid_32_chars():
    """Test BTIH with a valid 32-character hash."""
    valid_hash = "b" * 32
    btih_obj = util.BTIH(valid_hash)
    assert str(btih_obj) == valid_hash

def test_btih_invalid_length_short():
    """Test BTIH with a hash shorter than 32 characters."""
    with pytest.raises(ValueError, match="must be 32 or 40 characters long"):
        util.BTIH("a" * 31)

def test_btih_invalid_length_long():
    """Test BTIH with a hash longer than 40 characters."""
    with pytest.raises(ValueError, match="must be 32 or 40 characters long"):
        util.BTIH("a" * 41)

def test_btih_invalid_length_between():
    """Test BTIH with a hash length between 32 and 40."""
    with pytest.raises(ValueError, match="must be 32 or 40 characters long"):
        util.BTIH("a" * 35)

def test_btih_invalid_characters():
    """Test BTIH with invalid characters (hyphen)."""
    with pytest.raises(ValueError, match="contains invalid characters"):
        util.BTIH("a" * 10 + "-" + "b" * 29) # 40 chars total

def test_btih_invalid_type():
    """Test BTIH with a non-string input."""
    with pytest.raises(TypeError, match="Expected a string"):
        util.BTIH(12345)

# ===================================================================
# Tests for get_available_space_gb Function
# ===================================================================

# Use the 'mocker' fixture provided by pytest-mock
def test_get_available_space_gb_success(mocker):
    """Test successful retrieval of disk space."""
    # Mock shutil.disk_usage
    mock_disk_usage = mocker.patch('util.shutil.disk_usage')
    # Configure the mock return value (needs a 'free' attribute)
    mock_usage_result = MagicMock()
    mock_usage_result.free = 500 * (1024**3) # Simulate 500 GiB free
    mock_disk_usage.return_value = mock_usage_result

    # Call the function
    space_gb = util.get_available_space_gb("/fake/path")

    # Assertions
    assert space_gb == pytest.approx(500.0) # Use approx for float comparison
    mock_disk_usage.assert_called_once_with("/fake/path")

def test_get_available_space_gb_file_not_found(mocker):
    """Test handling of FileNotFoundError."""
    # Mock shutil.disk_usage to raise FileNotFoundError
    mock_disk_usage = mocker.patch('util.shutil.disk_usage', side_effect=FileNotFoundError("Path not found"))

    # Call the function
    space_gb = util.get_available_space_gb("/nonexistent/path")

    # Assertions
    assert space_gb is None
    mock_disk_usage.assert_called_once_with("/nonexistent/path")

def test_get_available_space_gb_other_exception(mocker):
    """Test handling of other exceptions."""
    # Mock shutil.disk_usage to raise a generic Exception
    mock_disk_usage = mocker.patch('util.shutil.disk_usage', side_effect=Exception("Some disk error"))

    # Call the function
    space_gb = util.get_available_space_gb("/error/path")

    # Assertions
    assert space_gb is None
    mock_disk_usage.assert_called_once_with("/error/path")


# ===================================================================
# Tests for get_dir_stats Function
# ===================================================================

# Patch os.path.isdir, os.walk, os.path.islink, os.path.getsize within the util module
@patch('util.os.path.isdir')
@patch('util.os.walk')
@patch('util.os.path.islink')
@patch('util.os.path.getsize')
def test_get_dir_stats_success(mock_getsize, mock_islink, mock_walk, mock_isdir, mocker):
    """Test calculating stats for a simple directory structure."""
    # Configure mocks
    mock_isdir.return_value = True # It is a directory
    mock_islink.return_value = False # No symlinks
    # Define the directory structure os.walk should return
    mock_walk.return_value = [
        ('/fake/dir', ['subdir'], ['file1.txt']), # Top level: 1 subdir, 1 file
        ('/fake/dir/subdir', [], ['file2.txt', 'file3.dat']), # Subdir: 0 subdirs, 2 files
    ]
    # Define file sizes returned by os.path.getsize
    # Needs to match the order files are processed by the mocked walk
    mock_getsize.side_effect = [100, 200, 300] # file1.txt=100, file2.txt=200, file3.dat=300

    # Call the function
    total_size, item_count = util.get_dir_stats('/fake/dir')

    # Assertions
    assert total_size == 100 + 200 + 300 # Sum of file sizes
    # item_count = 1 (top dir) + 1 (subdir) + 1 (file1) + 2 (file2, file3) = 5
    assert item_count == 5
    mock_isdir.assert_called_once_with('/fake/dir')
    mock_walk.assert_called_once_with('/fake/dir', topdown=True, onerror=mocker.ANY) # Check walk called correctly
    # Check getsize calls (adjust paths based on mock_walk structure)
    expected_getsize_calls = [
        call(os.path.join('/fake/dir', 'file1.txt')),
        call(os.path.join('/fake/dir/subdir', 'file2.txt')),
        call(os.path.join('/fake/dir/subdir', 'file3.dat')),
    ]
    mock_getsize.assert_has_calls(expected_getsize_calls)

@patch('util.os.path.isdir')
def test_get_dir_stats_not_a_directory(mock_isdir):
    """Test get_dir_stats when the path is not a directory."""
    mock_isdir.return_value = False # Simulate path not being a directory

    total_size, item_count = util.get_dir_stats('/fake/file')

    assert total_size == 0
    assert item_count == 0 # Should return 0,0 if not a directory
    mock_isdir.assert_called_once_with('/fake/file')

@patch('util.os.path.isdir')
@patch('util.os.walk')
def test_get_dir_stats_empty_directory(mock_walk, mock_isdir):
    """Test get_dir_stats with an empty directory."""
    mock_isdir.return_value = True
    # Simulate os.walk returning only the top directory with no contents
    mock_walk.return_value = [
        ('/fake/empty', [], []),
    ]

    total_size, item_count = util.get_dir_stats('/fake/empty')

    assert total_size == 0
    assert item_count == 1 # Only the directory itself
    mock_walk.assert_called_once()

# ===================================================================
# Tests for cleanup_destination Function
# ===================================================================

@patch('util.os.path.isdir')
@patch('util.os.path.isfile')
@patch('util.shutil.rmtree')
@patch('util.os.remove')
def test_cleanup_destination_directory(mock_remove, mock_rmtree, mock_isfile, mock_isdir):
    """Test cleanup for a directory path."""
    mock_isdir.return_value = True
    mock_isfile.return_value = False

    util.cleanup_destination("/fake/dir/to_delete")

    mock_isdir.assert_called_once_with("/fake/dir/to_delete")
    mock_isfile.assert_not_called() # Should not check isfile if isdir is True
    mock_rmtree.assert_called_once_with("/fake/dir/to_delete")
    mock_remove.assert_not_called()

@patch('util.os.path.isdir')
@patch('util.os.path.isfile')
@patch('util.shutil.rmtree')
@patch('util.os.remove')
def test_cleanup_destination_file(mock_remove, mock_rmtree, mock_isfile, mock_isdir):
    """Test cleanup for a file path."""
    mock_isdir.return_value = False
    mock_isfile.return_value = True

    util.cleanup_destination("/fake/file/to_delete.txt")

    mock_isdir.assert_called_once_with("/fake/file/to_delete.txt")
    mock_isfile.assert_called_once_with("/fake/file/to_delete.txt")
    mock_rmtree.assert_not_called()
    mock_remove.assert_called_once_with("/fake/file/to_delete.txt")

@patch('util.os.path.isdir')
@patch('util.os.path.isfile')
@patch('util.shutil.rmtree')
@patch('util.os.remove')
def test_cleanup_destination_not_found(mock_remove, mock_rmtree, mock_isfile, mock_isdir):
    """Test cleanup when the path doesn't exist."""
    mock_isdir.return_value = False
    mock_isfile.return_value = False # Path is neither file nor directory

    util.cleanup_destination("/fake/not_found")

    mock_isdir.assert_called_once_with("/fake/not_found")
    mock_isfile.assert_called_once_with("/fake/not_found")
    mock_rmtree.assert_not_called()
    mock_remove.assert_not_called()

@patch('util.os.path.isdir')
@patch('util.shutil.rmtree', side_effect=OSError("Permission denied"))
def test_cleanup_destination_directory_oserror(mock_rmtree, mock_isdir):
    """Test cleanup handles OSError during rmtree."""
    mock_isdir.return_value = True

    # Call cleanup, expect it to catch the OSError and print, not raise
    util.cleanup_destination("/fake/dir/permission_denied")

    mock_rmtree.assert_called_once() # Ensure rmtree was attempted


# ===================================================================
# Tests for verify_copy Function
# ===================================================================
# We already wrote some examples for this earlier, let's refine them

@patch('util.os.path.exists', return_value=True) # Assume paths exist for these tests
@patch('util.os.path.getsize')
def test_verify_copy_single_success(mock_getsize, mock_exists):
    mock_getsize.return_value = 5000
    assert util.verify_copy('src/file', 'dst/file', is_multi=False) is True
    assert mock_getsize.call_count == 2

@patch('util.os.path.exists', return_value=True)
@patch('util.os.path.getsize')
def test_verify_copy_single_fail(mock_getsize, mock_exists):
    mock_getsize.side_effect = [5000, 4999] # Different sizes
    assert util.verify_copy('src/file', 'dst/file', is_multi=False) is False
    assert mock_getsize.call_count == 2

@patch('util.os.path.exists', return_value=True)
@patch('util.get_dir_stats') # Mock the helper function directly
def test_verify_copy_multi_success(mock_get_stats, mock_exists):
    mock_get_stats.return_value = (10000, 10) # (size, count) - same for both calls
    assert util.verify_copy('src/dir', 'dst/dir', is_multi=True) is True
    assert mock_get_stats.call_count == 2

@patch('util.os.path.exists', return_value=True)
@patch('util.get_dir_stats')
def test_verify_copy_multi_fail_size(mock_get_stats, mock_exists):
    mock_get_stats.side_effect = [(10000, 10), (9999, 10)] # Size differs
    assert util.verify_copy('src/dir', 'dst/dir', is_multi=True) is False
    assert mock_get_stats.call_count == 2

@patch('util.os.path.exists', return_value=True)
@patch('util.get_dir_stats')
def test_verify_copy_multi_fail_count(mock_get_stats, mock_exists):
    mock_get_stats.side_effect = [(10000, 10), (10000, 9)] # Count differs
    assert util.verify_copy('src/dir', 'dst/dir', is_multi=True) is False
    assert mock_get_stats.call_count == 2

@patch('util.os.path.exists', side_effect=[True, False]) # Source exists, Dest does not
def test_verify_copy_dest_missing(mock_exists):
    assert util.verify_copy('src', 'dst', is_multi=False) is False
    assert mock_exists.call_count == 2 # Checks src then dst

