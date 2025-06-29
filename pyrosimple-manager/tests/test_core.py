import pytest
from unittest.mock import patch, MagicMock, call
import os
import shutil
from util import BTIH, TorrentInfo
from core import process_single_torrent, relocate_and_delete_ssd, notify_arr_manual_import, manage_ssd_space
import requests

# Example torrent data
EXAMPLE_TORRENT = TorrentInfo(
    hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'),
    name='daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv',
    path='\\downloading\\sonarr\\daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv',
    directory='/downloading/sonarr',
    size=5408683456,
    is_multi_file=False,
    label='sonarr'
)

# ===================================================================
# Tests for process_single_torrent
# ===================================================================

@pytest.fixture
def mock_engine():
    """Create a mock rTorrent engine for testing."""
    engine = MagicMock()
    engine.item.return_value = MagicMock()
    return engine

@pytest.fixture
def mock_config():
    """Mock the config module."""
    with patch('core.config') as mock_config:
        mock_config.DRY_RUN = False
        mock_config.COPY_RETRY_ATTEMPTS = 3
        mock_config.FINAL_DEST_BASE_HDD = '/downloads'
        yield mock_config

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
@patch('core.os.makedirs')
@patch('core.shutil.copy2')
def test_process_single_torrent_success(
    mock_copy2, mock_makedirs, mock_exists, mock_cleanup,
    mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test successful processing of a single torrent."""
    # Setup mocks
    mock_get_info.return_value = EXAMPLE_TORRENT
    mock_exists.return_value = False  # Destination doesn't exist
    mock_verify.return_value = True   # Copy verification succeeds

    # Call the function
    process_single_torrent(mock_engine, EXAMPLE_TORRENT.hash)

    # Verify calls
    mock_get_info.assert_called_once_with(mock_engine, EXAMPLE_TORRENT.hash)
    mock_exists.assert_called()
    mock_makedirs.assert_called()
    mock_copy2.assert_called_once()
    mock_verify.assert_called_once()

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
def test_process_single_torrent_existing_verified(
    mock_exists, mock_cleanup, mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test processing when destination exists and is verified."""
    # Setup mocks
    mock_get_info.return_value = EXAMPLE_TORRENT
    mock_exists.return_value = True   # Destination exists
    mock_verify.return_value = True   # Existing copy is verified

    # Call the function
    process_single_torrent(mock_engine, EXAMPLE_TORRENT.hash)

    # Verify calls
    mock_get_info.assert_called_once_with(mock_engine, EXAMPLE_TORRENT.hash)
    mock_exists.assert_called()
    mock_verify.assert_called_once()
    mock_cleanup.assert_not_called()  # Should not clean up verified copy

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
@patch('core.os.makedirs')
@patch('core.shutil.copy2')
def test_process_single_torrent_retry_success(
    mock_copy2, mock_makedirs, mock_exists, mock_cleanup,
    mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test successful processing after retry."""
    # Setup mocks
    mock_get_info.return_value = EXAMPLE_TORRENT
    mock_exists.side_effect = [False, True]  # First dest folder doesn't exist, second does
    mock_verify.side_effect = [False, True]  # First verify fails, second succeeds

    # Call the function
    process_single_torrent(mock_engine, EXAMPLE_TORRENT.hash)

    # Verify calls
    assert mock_verify.call_count == 2
    assert mock_cleanup.call_count == 1
    assert mock_copy2.call_count == 2

# ===================================================================
# Tests for relocate_and_delete_ssd
# ===================================================================

@patch('core.os.path.exists')
@patch('core.os.path.isdir')
@patch('core.os.path.isfile')
@patch('core.os.path.realpath')
@patch('core.os.path.normpath')
@patch('core.os.path.commonpath')
@patch('core.shutil.rmtree')
@patch('core.os.remove')
def test_relocate_and_delete_ssd_success(
    mock_remove, mock_rmtree, mock_commonpath, mock_normpath, mock_realpath,
    mock_isfile, mock_isdir, mock_exists, mock_engine, mock_config
):
    """Test successful relocation and deletion of SSD data."""
    # Setup mocks
    mock_engine.item.return_value = MagicMock()
    mock_engine.item.return_value.is_active = True
    mock_exists.return_value = True
    mock_isdir.return_value = False  # It's a file, not a directory
    mock_isfile.return_value = True  # It's a file, not a directory
    
    # Setup path normalization mocks
    mock_realpath.side_effect = lambda x: x  # Return path as is
    mock_normpath.side_effect = lambda x: x  # Return path as is
    mock_commonpath.return_value = '/downloading'  # Make safety check pass

    # Call the function
    result = relocate_and_delete_ssd(
        mock_engine,
        EXAMPLE_TORRENT,
        '/downloads',  # final_dest_base_hdd
        '/downloading'  # download_path_ssd
    )

    # Verify calls
    assert result is True
    mock_engine.item.return_value.stop.assert_called_once()
    mock_engine.item.return_value.start.assert_called_once()
    mock_remove.assert_called_once()

@patch('core.os.path.exists')
@patch('core.os.path.isdir')
@patch('core.os.path.isfile')
@patch('core.os.path.realpath')
@patch('core.os.path.normpath')
@patch('core.os.path.commonpath')
@patch('core.shutil.rmtree')
@patch('core.os.remove')
def test_relocate_and_delete_ssd_permission_error(
    mock_remove, mock_rmtree, mock_commonpath, mock_normpath, mock_realpath,
    mock_isfile, mock_isdir, mock_exists, mock_engine, mock_config
):
    """Test handling of permission errors during file operations."""
    # Setup mocks
    mock_engine.item.return_value = MagicMock()
    mock_engine.item.return_value.is_active = True
    mock_exists.return_value = True
    mock_isdir.return_value = False
    mock_isfile.return_value = True
    mock_remove.side_effect = PermissionError("Permission denied")
    
    # Setup path normalization mocks
    mock_realpath.side_effect = lambda x: x  # Return path as is
    mock_normpath.side_effect = lambda x: x  # Return path as is
    mock_commonpath.return_value = '/downloading'  # Make safety check pass

    # Call the function
    result = relocate_and_delete_ssd(
        mock_engine,
        EXAMPLE_TORRENT,
        '/downloads',
        '/downloading'
    )

    # Verify error handling
    assert result is False  # Should return False on permission error
    mock_engine.item.return_value.stop.assert_called_once()
    mock_engine.item.return_value.start.assert_called_once()  # Should attempt to restart torrent
    mock_remove.assert_called_once()  # Should attempt deletion once

# ===================================================================
# Tests for notify_arr_manual_import
# ===================================================================

@patch('core.requests.get')
def test_notify_arr_manual_import_success(mock_get, mock_config):
    """Test successful notification to Sonarr."""
    # Setup mocks
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_get.return_value = mock_response

    # Setup config
    mock_config.SONARR_URL = "http://sonarr:8989"
    mock_config.SONARR_API_KEY = "test-key"
    mock_config.DRY_RUN = False

    # Call the function
    notify_arr_manual_import("sonarr", EXAMPLE_TORRENT.hash, {
        "NOTIFY_ARR_ENABLED": True,
        "SONARR_URL": "http://sonarr:8989",
        "SONARR_API_KEY": "test-key"
    })

    # Verify calls
    mock_get.assert_called_once()
    assert "X-Api-Key" in mock_get.call_args[1]["headers"]
    assert str(EXAMPLE_TORRENT.hash) in mock_get.call_args[1]["params"]["downloadId"]

# ===================================================================
# Additional Test Scenarios
# ===================================================================

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
@patch('core.os.makedirs')
@patch('core.shutil.copy2')
def test_process_single_torrent_error_handling(
    mock_copy2, mock_makedirs, mock_exists, mock_cleanup,
    mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test error handling in process_single_torrent."""
    # Setup mocks for various error scenarios
    mock_get_info.return_value = EXAMPLE_TORRENT
    mock_exists.return_value = False
    mock_copy2.side_effect = OSError("Permission denied")
    mock_verify.return_value = False

    # Call the function
    process_single_torrent(mock_engine, EXAMPLE_TORRENT.hash)

    # Verify error handling
    assert mock_copy2.call_count == mock_config.COPY_RETRY_ATTEMPTS  # Should try all retry attempts

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
@patch('core.os.makedirs')
@patch('core.shutil.copytree')
def test_process_single_torrent_multi_file(
    mock_copytree, mock_makedirs, mock_exists, mock_cleanup,
    mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test handling of multi-file torrents."""
    # Create a multi-file torrent example
    multi_file_torrent = TorrentInfo(
        hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'),
        name='multi_file_torrent',
        path='/downloading/sonarr/multi_file_torrent',
        directory='/downloading/sonarr',
        size=5408683456,
        is_multi_file=True,
        label='sonarr'
    )

    # Setup mocks
    mock_get_info.return_value = multi_file_torrent
    mock_exists.return_value = False
    mock_verify.return_value = True

    # Call the function
    process_single_torrent(mock_engine, multi_file_torrent.hash)

    # Verify multi-file handling
    mock_copytree.assert_called_once()  # Should use copytree for directories
    mock_verify.assert_called_once()
    assert mock_copytree.call_args[1].get('dirs_exist_ok', False)  # Should use dirs_exist_ok

@patch('core.get_torrent_info')
@patch('core.verify_copy')
@patch('core.cleanup_destination')
@patch('core.os.path.exists')
@patch('core.os.makedirs')
@patch('core.shutil.copy2')
def test_process_single_torrent_dry_run(
    mock_copy2, mock_makedirs, mock_exists, mock_cleanup,
    mock_verify, mock_get_info, mock_engine, mock_config
):
    """Test dry-run mode functionality."""
    # Setup mocks
    mock_get_info.return_value = EXAMPLE_TORRENT
    mock_exists.return_value = False
    mock_config.DRY_RUN = True  # Enable dry-run mode

    # Call the function
    process_single_torrent(mock_engine, EXAMPLE_TORRENT.hash)

    # Verify dry-run behavior
    mock_copy2.assert_not_called()  # Should not perform actual copy
    mock_cleanup.assert_not_called()  # Should not perform actual cleanup
    mock_verify.assert_not_called()  # Should not perform actual verification

@patch('core.requests.get')
def test_notify_arr_manual_import_failure(mock_get, mock_config):
    """Test handling of failed API notifications."""
    # Setup mocks for various failure scenarios
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    # Setup config
    mock_config.SONARR_URL = "http://sonarr:8989"
    mock_config.SONARR_API_KEY = "test-key"
    mock_config.DRY_RUN = False

    # Test HTTP error
    notify_arr_manual_import("sonarr", EXAMPLE_TORRENT.hash, {
        "NOTIFY_ARR_ENABLED": True,
        "SONARR_URL": "http://sonarr:8989",
        "SONARR_API_KEY": "test-key"
    })
    mock_get.assert_called_once()

    # Test connection error
    mock_get.reset_mock()
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    notify_arr_manual_import("sonarr", EXAMPLE_TORRENT.hash, {
        "NOTIFY_ARR_ENABLED": True,
        "SONARR_URL": "http://sonarr:8989",
        "SONARR_API_KEY": "test-key"
    })
    mock_get.assert_called_once()

# ===================================================================
# Tests for manage_ssd_space
# ===================================================================

@patch('core.get_available_space_gb')
@patch('util.get_torrents_by_path')
def test_manage_ssd_space_sufficient_space(
    mock_get_torrents, mock_get_space, mock_engine, mock_config
):
    """Test when SSD space is sufficient (no cleanup needed)."""
    # Setup mocks
    mock_get_space.return_value = 100.0  # 100GB available
    mock_config.DISK_SPACE_THRESHOLD_GB = 50.0  # 50GB threshold
    mock_get_torrents.return_value = []  # No torrents needed

    # Call the function
    manage_ssd_space(mock_engine)

    # Verify behavior
    mock_get_space.assert_called_once_with(mock_config.DOWNLOAD_PATH_SSD)
    mock_get_torrents.assert_not_called()  # Should not look for torrents if space is sufficient

@patch('core.get_available_space_gb')
@patch('core.relocate_and_delete_ssd')
def test_manage_ssd_space_no_eligible_torrents(
    mock_relocate, mock_get_space, mock_engine, mock_config
):
    """Test when SSD space is low but no eligible torrents are found."""
    # Setup mocks
    mock_get_space.return_value = 20.0  # 20GB available
    mock_config.DISK_SPACE_THRESHOLD_GB = 50.0  # 50GB threshold
    mock_engine.items.return_value = []  # No eligible torrents

    # Call the function
    manage_ssd_space(mock_engine)

    # Verify behavior
    mock_get_space.assert_called_once_with(mock_config.DOWNLOAD_PATH_SSD)
    mock_engine.items.assert_called_once()
    mock_relocate.assert_not_called()  # Should not attempt relocation

@patch('core.get_available_space_gb')
@patch('core.relocate_and_delete_ssd')
def test_manage_ssd_space_successful_relocation(
    mock_relocate, mock_get_space, mock_engine, mock_config
):
    """Test successful relocation of torrents to free up space."""
    # Setup test data
    torrent1 = TorrentInfo(
        hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'),
        name='test1.mkv',
        path='/downloading/sonarr/test1.mkv',
        directory='/downloading/sonarr',
        size=10 * 1024**3,  # 10GB
        is_multi_file=False,
        label='sonarr'
    )
    torrent2 = TorrentInfo(
        hash=BTIH('12E5A8D9F7800A063237F0D37467144360D4B70B'),
        name='test2.mkv',
        path='/downloading/sonarr/test2.mkv',
        directory='/downloading/sonarr',
        size=20 * 1024**3,  # 20GB
        is_multi_file=False,
        label='sonarr'
    )

    # Setup mocks
    mock_get_space.return_value = 20.0  # 20GB available
    mock_config.DISK_SPACE_THRESHOLD_GB = 50.0  # 50GB threshold
    mock_config.DOWNLOAD_PATH_SSD = '/downloading'  # Set the SSD path
    
    # Create mock items with completion status and timestamps
    mock_item1 = MagicMock()
    mock_item1.hash = torrent1.hash
    mock_item1.name = torrent1.name
    mock_item1.path = torrent1.path
    mock_item1.directory = torrent1.directory
    mock_item1.size = torrent1.size
    mock_item1.complete = True
    mock_item1.tm_completed = 1000  # Valid timestamp
    mock_item1.custom1 = torrent1.label
    mock_item1.is_multi_file = False  # Set is_multi_file attribute
    
    mock_item2 = MagicMock()
    mock_item2.hash = torrent2.hash
    mock_item2.name = torrent2.name
    mock_item2.path = torrent2.path
    mock_item2.directory = torrent2.directory
    mock_item2.size = torrent2.size
    mock_item2.complete = True
    mock_item2.tm_completed = 2000  # Valid timestamp
    mock_item2.custom1 = torrent2.label
    mock_item2.is_multi_file = False  # Set is_multi_file attribute
    
    mock_engine.items.return_value = [mock_item1, mock_item2]
    mock_relocate.return_value = True  # Relocation always succeeds

    # Call the function
    manage_ssd_space(mock_engine)

    # Verify behavior
    mock_get_space.assert_called_once_with(mock_config.DOWNLOAD_PATH_SSD)
    mock_engine.items.assert_called_once()
    assert mock_relocate.call_count == 2  # Should attempt to relocate both torrents
    # Verify correct arguments for each call
    mock_relocate.assert_has_calls([
        call(mock_engine, torrent1, mock_config.FINAL_DEST_BASE_HDD, mock_config.DOWNLOAD_PATH_SSD),
        call(mock_engine, torrent2, mock_config.FINAL_DEST_BASE_HDD, mock_config.DOWNLOAD_PATH_SSD)
    ])

@patch('core.get_available_space_gb')
@patch('core.relocate_and_delete_ssd')
def test_manage_ssd_space_relocation_failure(
    mock_relocate, mock_get_space, mock_engine, mock_config
):
    """Test handling of relocation failures."""
    # Setup test data
    torrent1 = TorrentInfo(
        hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'),
        name='test1.mkv',
        path='/downloading/sonarr/test1.mkv',
        directory='/downloading/sonarr',
        size=10 * 1024**3,  # 10GB
        is_multi_file=False,
        label='sonarr'
    )
    torrent2 = TorrentInfo(
        hash=BTIH('12E5A8D9F7800A063237F0D37467144360D4B70B'),
        name='test2.mkv',
        path='/downloading/sonarr/test2.mkv',
        directory='/downloading/sonarr',
        size=20 * 1024**3,  # 20GB
        is_multi_file=False,
        label='sonarr'
    )

    # Setup mocks
    mock_get_space.return_value = 20.0  # 20GB available
    mock_config.DISK_SPACE_THRESHOLD_GB = 50.0  # 50GB threshold
    mock_config.DOWNLOAD_PATH_SSD = '/downloading'  # Set the SSD path
    
    # Create mock items with completion status and timestamps
    mock_item1 = MagicMock()
    mock_item1.hash = torrent1.hash
    mock_item1.name = torrent1.name
    mock_item1.path = torrent1.path
    mock_item1.directory = torrent1.directory
    mock_item1.size = torrent1.size
    mock_item1.complete = True
    mock_item1.tm_completed = 1000  # Valid timestamp
    mock_item1.custom1 = torrent1.label
    mock_item1.is_multi_file = False  # Set is_multi_file attribute
    
    mock_item2 = MagicMock()
    mock_item2.hash = torrent2.hash
    mock_item2.name = torrent2.name
    mock_item2.path = torrent2.path
    mock_item2.directory = torrent2.directory
    mock_item2.size = torrent2.size
    mock_item2.complete = True
    mock_item2.tm_completed = 2000  # Valid timestamp
    mock_item2.custom1 = torrent2.label
    mock_item2.is_multi_file = False  # Set is_multi_file attribute
    
    mock_engine.items.return_value = [mock_item1, mock_item2]
    mock_relocate.side_effect = [True, False]  # First relocation succeeds, second fails

    # Call the function
    manage_ssd_space(mock_engine)

    # Verify behavior
    mock_get_space.assert_called_once_with(mock_config.DOWNLOAD_PATH_SSD)
    mock_engine.items.assert_called_once()
    assert mock_relocate.call_count == 2  # Should attempt both torrents
    # Verify correct arguments for each call
    mock_relocate.assert_has_calls([
        call(mock_engine, torrent1, mock_config.FINAL_DEST_BASE_HDD, mock_config.DOWNLOAD_PATH_SSD),
        call(mock_engine, torrent2, mock_config.FINAL_DEST_BASE_HDD, mock_config.DOWNLOAD_PATH_SSD)
    ])
