#!/usr/bin/env python3

import os
import shutil
import time
import requests
import typing
from util import (
    get_torrent_info, verify_copy,
    get_available_space_gb, cleanup_destination,
    TimeoutError, file_lock, get_lock_file_path
)
# Import configuration constants
import config
from pyrosimple.torrent import engine as rtorrent_engine # For field registry access

# Import logging
try:
    from logger import setup_logging
    logger = setup_logging('pyrosimple-manager-core')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('pyrosimple-manager-core')

if typing.TYPE_CHECKING:
    from pyrosimple.torrent.rtorrent import RtorrentItem
    from pyrosimple.torrent.rtorrent import RtorrentEngine
    from util import TorrentInfo, BTIH

# ===================================================================
# Core Action Functions
# ===================================================================
def notify_arr_scan_downloads(service_type, download_id: 'BTIH', arr_config, hdd_path: str = None):
    """Notifies Sonarr or Radarr to scan for completed downloads using the command API.
    
    Args:
        service_type: Either 'sonarr' or 'radarr'
        download_id: Torrent hash for downloadClientId parameter
        arr_config: Configuration dictionary containing URLs and API keys
        hdd_path: Path where the movie/episode was moved to on HDD
    """
    if not arr_config.get("NOTIFY_ARR_ENABLED", False): 
        logger.info("Arr notification disabled, skipping.")
        return

    if service_type == "sonarr":
        base_url = arr_config.get("SONARR_URL", "").rstrip('/')
        api_key = arr_config.get("SONARR_API_KEY", "")
        service_name = "Sonarr"
        command_name = "DownloadedEpisodesScan"  # Sonarr equivalent
    elif service_type == "radarr":
        base_url = arr_config.get("RADARR_URL", "").rstrip('/')
        api_key = arr_config.get("RADARR_API_KEY", "")
        service_name = "Radarr"
        command_name = "DownloadedMoviesScan"  # Radarr command for scanning downloaded movies
    else: 
        logger.warning(f"Unknown service type '{service_type}' for notification.")
        return
        
    if not base_url or not api_key: 
        logger.warning(f"{service_name} URL or API Key not configured. Skipping notification.")
        return

    # Use the correct command API endpoint
    api_endpoint = f"{base_url}/api/v3/command"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Prepare command payload with downloadClientId and path for targeted scanning
    payload = {
        "name": command_name,
        "downloadClientId": str(download_id)
    }
    
    # Add path parameter if provided for more targeted scanning
    if hdd_path:
        payload["path"] = hdd_path
        logger.info(f"Will scan specific path: {hdd_path}")
    
    if config.DRY_RUN:
        logger.info(f"[DRY RUN] Would notify {service_name} via POST {api_endpoint}")
        logger.info(f"[DRY RUN] Command: {payload}")
        return
    
    logger.info(f"Notifying {service_name} to scan for downloaded content...")
    logger.info(f"Sending command '{command_name}' with downloadClientId: {download_id}")
    if hdd_path:
        logger.info(f"Target path: {hdd_path}")
    
    try:
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"{service_name} command sent successfully (Status: {response.status_code}).")
            try: 
                response_json = response.json()
                command_id = response_json.get('id', 'Unknown')
                logger.info(f"Command queued with ID: {command_id}")
                logger.debug(f"Response: {str(response_json)[:200]}...")
            except requests.exceptions.JSONDecodeError: 
                logger.debug(f"Response Text: {response.text[:200]}...")
        else: 
            logger.warning(f"{service_name} command returned unexpected status: {response.status_code}")
            logger.debug(f"Response: {response.text[:200]}...")
            
    except requests.exceptions.RequestException as e: 
        logger.error(f"ERROR notifying {service_name}: {e}")
    except Exception as e: 
        logger.error(f"Unexpected error during {service_name} notification: {e}")


def relocate_and_delete_ssd(engine: 'RtorrentEngine', torrent_info: 'TorrentInfo', final_dest_base_hdd: str, download_path_ssd: str):
    """ Stops torrent, sets rTorrent dir to HDD path, deletes SSD copy, restarts. Uses pyrosimple engine."""
    hdd_base_dir = os.path.join(final_dest_base_hdd, torrent_info.label)
    logger.info(f"Attempting relocation for {torrent_info.hash} ('{torrent_info.name}'):")
    logger.info(f"SSD path (to delete): {torrent_info.path}")
    logger.info(f"Target HDD base dir (for rTorrent): {hdd_base_dir}")

    if config.DRY_RUN:
        logger.info(f"[DRY RUN] Would relocate torrent {torrent_info.hash} from SSD to HDD")
        logger.info(f"[DRY RUN] Would stop torrent, update directory to {hdd_base_dir}, delete {torrent_info.path}, restart torrent")
        return True

    was_started = False; start_successful = True; delete_successful = False

    try:
        # Get item, prefetch needed state info
        prefetch_fields = ['is_active']
        prefetch = [item for f in prefetch_fields for item in rtorrent_engine.FIELD_REGISTRY[f].requires]
        item: 'RtorrentItem' = engine.item(torrent_info.hash, prefetch=prefetch)
        if item is None: 
            logger.error(f"Torrent {torrent_info.hash} not found for relocation.")
            return False

        logger.info("Checking torrent state via pyrosimple...")
        if item.is_active:
            logger.info("Torrent is active. Stopping via pyrosimple...")
            was_started = True
            item.stop()
            logger.info("Stop command sent.")
            time.sleep(1)
        else: 
            logger.info("Torrent is already stopped.")

        logger.info("Updating rTorrent directory via pyrosimple RPC call...")
        item.rpc_call("d.directory.set", [hdd_base_dir])
        logger.info("Successfully executed d.directory.set via RPC.")
        time.sleep(0.5)

        # CRITICAL: Verify destination exists before deleting source
        expected_hdd_path = os.path.join(hdd_base_dir, torrent_info.name.strip())
        logger.info(f"Verifying destination exists at: {expected_hdd_path}")
        
        if not os.path.exists(expected_hdd_path):
            logger.warning(f"Destination path '{expected_hdd_path}' does not exist!")
            logger.info(f"Need to copy data from SSD to HDD first...")
            
            if config.DRY_RUN:
                logger.info(f"[DRY RUN] Would copy {'directory' if torrent_info.is_multi_file else 'file'} from {torrent_info.path} to {expected_hdd_path}")
            else:
                try:
                    # Ensure base directory exists
                    os.makedirs(hdd_base_dir, exist_ok=True)
                    
                    copy_start_time = time.time()
                    if torrent_info.is_multi_file:
                        shutil.copytree(torrent_info.path, expected_hdd_path, copy_function=shutil.copy2, dirs_exist_ok=True)
                    else:
                        shutil.copy2(torrent_info.path, expected_hdd_path)
                    logger.info(f"Copy completed in {time.time() - copy_start_time:.2f} seconds.")
                    
                    # Verify the copy was successful
                    from util import verify_copy
                    if not verify_copy(torrent_info.path, expected_hdd_path, torrent_info.is_multi_file):
                        logger.error(f"Copy verification failed!")
                        if was_started: 
                            logger.info("Attempting to restart torrent after copy failure...")
                            item.start()
                        return False
                    logger.info(f"Copy verification successful.")
                    
                except (shutil.Error, OSError) as e:
                    logger.error(f"Failed to copy data to HDD: {e}")
                    if was_started: 
                        logger.info("Attempting to restart torrent after copy failure...")
                        item.start()
                    return False
        else:
            logger.info(f"Destination already exists on HDD.")

        logger.info(f"Destination verified. Proceeding to delete SSD data at: {torrent_info.path}")
        
        # Safety check before deletion
        try:
            norm_ssd_dl_path = os.path.normpath(os.path.realpath(download_path_ssd))
            norm_ssd_data_path = os.path.normpath(os.path.realpath(torrent_info.path))
            if os.path.commonpath([norm_ssd_data_path, norm_ssd_dl_path]) != norm_ssd_dl_path:
                logger.error(f"SAFETY ERROR: Path '{norm_ssd_data_path}' not within '{norm_ssd_dl_path}'. Aborting delete.")
                if was_started: 
                    logger.info("Attempting to restart torrent after safety check failure...")
                    item.start()
                return False
        except FileNotFoundError: 
            logger.warning(f"SSD path '{torrent_info.path}' not found for safety check.")
            delete_successful = True
        except Exception as e: 
            logger.error(f"Error during safety check: {e}")
            return False

        # Delete SSD data only if safety check passed/path already gone
        if not delete_successful:
            try:
                if os.path.exists(torrent_info.path):
                    if os.path.isdir(torrent_info.path): 
                        shutil.rmtree(torrent_info.path)
                        logger.info(f"Successfully deleted SSD directory.")
                    elif os.path.isfile(torrent_info.path): 
                        os.remove(torrent_info.path)
                        logger.info(f"Successfully deleted SSD file.")
                    delete_successful = True
                else: 
                    logger.warning(f"SSD path not found for deletion (already gone).")
                    delete_successful = True
            except OSError as e: 
                logger.error(f"Error deleting SSD data: {e}")
                delete_successful = False

        # Restart torrent if it was originally running
        if was_started:
            logger.info("Restarting torrent via pyrosimple...")
            item.start()
            logger.info("Start command sent.")
            start_successful = True # Assume success if no exception

        return delete_successful and start_successful

    except Exception as e:
        logger.error(f"pyrosimple request error during relocation of {torrent_info.hash}: {e}")
        if was_started and "start" not in str(e).lower():
            try: 
                logger.info("Attempting to restart torrent after pyrosimple error...")
                engine.item(torrent_info.hash).start()
            except Exception as restart_e: 
                logger.error(f"Failed to send restart command after error: {restart_e}")
        return False
# ===================================================================

# ===================================================================
# Main Processing Functions (Orchestration Logic)
# ===================================================================
def process_single_torrent(engine: 'RtorrentEngine', hash_val: 'BTIH'):
    """Orchestrates copy, verify (with retries), and notify Arr for a specific finished torrent."""
    logger.info(f"--- Processing finished torrent (Copy/Verify/Notify phase): {hash_val} ---")
    start_process_time = time.time()
    copy_verified = False # Flag to track if copy is successfully verified

    # 1. Get Info using the utility function with improved error handling
    try:
        info = get_torrent_info(engine, hash_val, wait_for_stability=True)
    except TimeoutError:
        logger.error(f"Timeout getting torrent info for {hash_val}. This may indicate the torrent is stuck in checking state.")
        logger.error(f"Exiting processing for {hash_val} due to timeout.")
        return
    except Exception as e:
        logger.error(f"Failed to get torrent info for {hash_val} after retries: {e}")
        logger.error(f"Exiting processing for {hash_val} due to info fetch failure.")
        return
    
    if info is None:
        logger.error(f"Exiting processing for {hash_val} due to info fetch failure.")
        return # Exit if info fetching failed

    # Extract needed variables
    is_multi = info.is_multi_file  # Use correct attribute name
    ssd_data_path = info.path
    tag = info.label  # Use correct attribute name

    # 2. Construct Paths using config paths
    hdd_base_dir = os.path.join(config.FINAL_DEST_BASE_HDD, tag)
    hdd_data_path = os.path.join(hdd_base_dir, info.name.strip())
    logger.info(f"Source SSD Path: {ssd_data_path}")
    logger.info(f"Target HDD Path: {hdd_data_path}")
    logger.info(f"Torrent Tag: {tag}")

    # 3. Pre-Copy Check: Handle existing destination from previous script run
    if os.path.exists(hdd_data_path):
        logger.warning(f"Destination path '{hdd_data_path}' already exists.")
        # Call verify_copy from util
        if verify_copy(ssd_data_path, hdd_data_path, is_multi):
            logger.info("Existing destination verified successfully. Skipping copy.")
            copy_verified = True # Treat existing verified copy as success
        else:
            logger.warning("Existing destination failed verification. Attempting cleanup and fresh copy.")
            cleanup_destination(hdd_data_path) # Call cleanup from util

    # 4. Copy & Verify Loop (if not already verified)
    if not copy_verified:
        # Use retry attempts from config
        max_attempts = max(1, config.COPY_RETRY_ATTEMPTS)
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Copy attempt {attempt}/{max_attempts}...")

            # Clean up destination from *previous failed attempt within this loop*
            if attempt > 1 and os.path.exists(hdd_data_path):
                 logger.info("Cleaning up destination from previous failed attempt...")
                 cleanup_destination(hdd_data_path) # Call cleanup from util

            # Attempt Copy
            copy_succeeded_this_attempt = False
            try:
                # Ensure base directory exists before copy
                os.makedirs(hdd_base_dir, exist_ok=True)
                copy_start_time = time.time()
                
                if config.DRY_RUN:
                    logger.info(f"[DRY RUN] Would copy {'directory' if is_multi else 'file'} from {ssd_data_path} to {hdd_data_path}")
                    copy_succeeded_this_attempt = True
                else:
                    if is_multi:
                        shutil.copytree(ssd_data_path, hdd_data_path, copy_function=shutil.copy2, dirs_exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(hdd_data_path), exist_ok=True)
                        shutil.copy2(ssd_data_path, hdd_data_path)
                    logger.info(f"Copy finished in {time.time() - copy_start_time:.2f} seconds (Attempt {attempt}).")
                    copy_succeeded_this_attempt = True
            except (shutil.Error, OSError) as e:
                logger.error(f"Error during copy (Attempt {attempt}): {e}")

            # Attempt Verification (only if copy didn't raise exception)
            if copy_succeeded_this_attempt:
                # In dry-run mode, assume verification would pass
                if config.DRY_RUN:
                    logger.info(f"[DRY RUN] Would verify copy integrity")
                    copy_verified = True; break
                # Call verify_copy from util
                elif verify_copy(ssd_data_path, hdd_data_path, is_multi):
                    copy_verified = True; break # Success! Exit loop.
                else:
                    logger.warning(f"Verification failed on attempt {attempt}.") # Loop continues

            # If this was the last attempt and we still haven't verified, log failure
            if attempt == max_attempts and not copy_verified:
                logger.error(f"Failed to copy and verify after {max_attempts} attempts.")
                break

    # 5. Notification Phase (only if copy was successfully verified)
    if copy_verified:
        logger.info("Copy successful and verified. Notifying Arr service...")
        service_to_notify = None
        # Determine which service to notify based on tag (using config tags)
        if tag.lower() == config.SONARR_TAG.lower(): service_to_notify = "sonarr"
        elif tag.lower() == config.RADARR_TAG.lower(): service_to_notify = "radarr"
        else: logger.info(f"Tag '{tag}' does not match Sonarr/Radarr tags. Skipping notification.")

        # If a matching service was found, send the notification
        if service_to_notify:
            # Call notify_arr_scan_downloads, passing the config dict
            notify_arr_scan_downloads(service_to_notify, hash_val, config.ARR_CONFIG, hdd_data_path)

        logger.info(f"--- Successfully processed Copy/Verify/Notify for: {hash_val} ---")
    else:
         logger.error(f"--- Failed Copy/Verify/Notify phase for: {hash_val} ---")
         if os.path.exists(hdd_data_path): cleanup_destination(hdd_data_path) # Final cleanup

    logger.info(f"--- Finished Copy/Verify/Notify phase for {hash_val} in {time.time() - start_process_time:.2f} seconds ---")


def manage_ssd_space(engine: 'RtorrentEngine'):
    """Checks SSD space and relocates oldest completed torrents from SSD to HDD if needed."""
    logger.info("--- Checking SSD Space and Managing Older Torrents ---")
    
    # Use file locking to prevent race conditions
    lock_file = get_lock_file_path('space_management')
    
    try:
        with file_lock(lock_file, timeout=5):
            logger.info("Acquired space management lock - proceeding with space check")
            _manage_ssd_space_locked(engine)
    except Exception as e:
        if "Could not acquire lock" in str(e):
            logger.info("Space management already running in another process - skipping")
        else:
            logger.error(f"Error during space management: {e}")

def _manage_ssd_space_locked(engine: 'RtorrentEngine'):
    """Internal space management function that runs with lock acquired"""
    # Use get_available_space_gb from util, passing config path
    available_gb = get_available_space_gb(config.DOWNLOAD_PATH_SSD)
    if available_gb is None: 
        logger.error("Could not check SSD space. Skipping management.")
        return

    logger.info(f"Available SSD space: {available_gb:.2f} GB. Threshold: {config.DISK_SPACE_THRESHOLD_GB} GB.")
    # Use threshold from config
    if available_gb >= config.DISK_SPACE_THRESHOLD_GB: 
        logger.info("SSD space sufficient. No cleanup needed.")
        return

    space_needed = config.DISK_SPACE_THRESHOLD_GB - available_gb
    logger.warning(f"SSD space below threshold. Need to free up {space_needed:.2f} GB.")
    logger.info("Finding completed torrents residing on SSD for potential relocation via pyrosimple...")

    sorted_torrents_on_ssd = [] # List to hold info
    try:
        prefetch_fields = ['hash', 'name', 'path', 'directory', 'size',
                            'is_complete', 'label', 'completed', 'is_multi_file']
        prefetch = [item for f in prefetch_fields for item in rtorrent_engine.FIELD_REGISTRY[f].requires]

        items_on_ssd_candidates = []
        logger.debug(f"Prefetching fields: {prefetch_fields}")
        all_items = engine.items(prefetch=prefetch) # Use engine from util
        logger.info(f"Filtering torrents for SSD candidates...")

        for item in all_items: # Filter items in Python
            try:
                is_complete = getattr(item, 'is_complete', False)
                # Use directory path from config
                item_dir = getattr(item, 'directory', None)

                if is_complete and item_dir and item_dir.startswith(config.DOWNLOAD_PATH_SSD):
                    completed = getattr(item, 'completed', 0)
                    if not isinstance(completed, int) or completed <= 0:
                         logger.warning(f"Skipping item {item.hash} due to missing or invalid completed value: {completed}")
                         continue
                    # Create TorrentInfo object for relocation function
                    from util import TorrentInfo, BTIH
                    torrent_info = TorrentInfo(
                        hash=BTIH(item.hash),
                        name=item.name,
                        path=item.path,
                        directory=item.directory,
                        size=item.size,
                        is_multi_file=getattr(item, 'is_multi_file', False),
                        label=getattr(item, 'label', '')
                    )
                    info = {
                        "torrent_info": torrent_info,
                        "size": item.size/(1024**3),
                        "timestamp": completed
                    }
                    items_on_ssd_candidates.append(info)
            except AttributeError as e: 
                logger.warning(f"Attribute error processing item {getattr(item, 'hash', 'UNKNOWN')}: {e}")
            except Exception as e: 
                logger.warning(f"Unexpected error processing item {getattr(item, 'hash', 'UNKNOWN')}: {e}")

        # Sort the collected list by timestamp (oldest first)
        sorted_torrents_on_ssd = sorted(items_on_ssd_candidates, key=lambda x: x['timestamp'])

    except Exception as e: 
        logger.error(f"Failed to get list of torrents for space management: {e}")
        return

    if not sorted_torrents_on_ssd: 
        logger.info("No eligible completed torrents found on SSD to relocate.")
        return
    logger.info(f"Found {len(sorted_torrents_on_ssd)} completed torrent(s) on SSD to consider for relocation (oldest first).")

    # Relocate Oldest Torrents until Space Threshold is Met
    space_freed_gb = 0; relocated_count = 0
    for info in sorted_torrents_on_ssd:
        if space_freed_gb >= space_needed: 
            logger.info(f"Successfully freed {space_freed_gb:.2f} GB.")
            break
        # Call the relocation function, passing TorrentInfo object
        if relocate_and_delete_ssd(engine, info["torrent_info"], config.FINAL_DEST_BASE_HDD, config.DOWNLOAD_PATH_SSD):
            space_freed_gb += info["size"]; relocated_count += 1
        else: 
            logger.error(f"Stopping relocation process due to failure on {info['torrent_info'].hash}.")
            break

    logger.info(f"Space Management Summary: Relocated {relocated_count} older torrent(s), freeing approx {space_freed_gb:.2f} GB.")
    final_available_space = available_gb + space_freed_gb
    logger.info(f"Estimated available SSD space is now {final_available_space:.2f} GB.")
# ===================================================================

