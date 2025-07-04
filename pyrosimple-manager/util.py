#!/usr/bin/env python3

import os
import re
import shutil
import time
import signal
import functools
import fcntl
from contextlib import contextmanager
from pyrosimple.torrent.engine import FIELD_REGISTRY
from pyrosimple.util import matching
import typing
from dataclasses import dataclass

# Import logging
try:
    from logger import setup_logging
    logger = setup_logging('pyrosimple-manager-util')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('pyrosimple-manager-util')

if typing.TYPE_CHECKING:
    from pyrosimple.torrent.rtorrent import RtorrentItem
    from pyrosimple.torrent.rtorrent import RtorrentEngine

# ===================================================================
# Helper Classes and Exceptions
# ===================================================================
class BTIH(str):
    """
    Represents a BitTorrent Info Hash (BTIH) string.

    Enforces that the value is a string of exactly 32 or 40 characters
    containing only alphanumeric characters (a-z, A-Z, 0-9).
    """
    # Pre-compile regex for efficiency
    _VALID_BTIH_PATTERN = re.compile(r'^[a-zA-Z0-9]{32}$|^[a-zA-Z0-9]{40}$')

    def __new__(cls, value):
        # Basic type check
        if not isinstance(value, str):
            raise TypeError(f"Expected a string for BTIH, but got {type(value).__name__}")

        # Length check
        length = len(value)
        if length != 32 and length != 40:
            raise ValueError(f"BTIH must be 32 or 40 characters long, got {length}")

        # Character set check (Alternative using regex)
        if not cls._VALID_BTIH_PATTERN.fullmatch(value):
             raise ValueError("BTIH contains invalid characters. Only a-z, A-Z, 0-9 are allowed.")

        # If all checks pass, create the string object using the parent's __new__
        instance = super().__new__(cls, value)
        return instance

    def __repr__(self):
        return f"BTIH('{super().__str__()}')"

@dataclass
class TorrentInfo:
    hash: BTIH
    name: str
    path: str
    directory: str
    size: int
    is_multi_file: bool
    label: str

class TimeoutError(Exception):
    """Raised when an operation times out"""
    pass

class LockError(Exception):
    """Raised when unable to acquire a required lock"""
    pass

# ===================================================================
# Locking Utilities
# ===================================================================
@contextmanager
def file_lock(lock_file_path, timeout=10):
    """
    File-based locking mechanism to prevent race conditions.
    Uses fcntl for POSIX systems (Linux containers) with exponential backoff.
    """
    lock_file = None
    try:
        # Create lock file directory if it doesn't exist
        lock_dir = os.path.dirname(lock_file_path)
        os.makedirs(lock_dir, exist_ok=True)
        
        # Open lock file
        lock_file = open(lock_file_path, 'w')
        
        # Try to acquire lock with exponential backoff
        start_time = time.time()
        attempt = 0
        max_delay = 2.0  # Maximum delay between attempts
        
        while time.time() - start_time < timeout:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"Acquired lock: {lock_file_path}")
                
                # Write PID to lock file for debugging
                lock_file.write(f"{os.getpid()}\n")
                lock_file.flush()
                
                yield  # Lock acquired successfully
                return
                
            except IOError:
                attempt += 1
                # Exponential backoff with jitter
                delay = min(0.1 * (2 ** attempt), max_delay)
                # Add small random jitter to prevent thundering herd
                import random
                delay += random.uniform(0, 0.1)
                
                time.sleep(delay)
        
        # Timeout occurred
        raise LockError(f"Could not acquire lock {lock_file_path} within {timeout} seconds")
        
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                # Remove lock file
                if os.path.exists(lock_file_path):
                    os.unlink(lock_file_path)
                logger.debug(f"Released lock: {lock_file_path}")
            except Exception as e:
                logger.warning(f"Error releasing lock {lock_file_path}: {e}")

def get_lock_file_path(lock_name):
    """Get the full path for a lock file"""
    import config
    return os.path.join(config.LOCK_DIR, f"{lock_name}.lock")

def get_queue_dir():
    """Get the directory path for pending torrent queue"""
    import config
    return os.path.join(config.LOCK_DIR, 'queue')

def queue_torrent_for_processing(hash_val):
    """Add a torrent hash to the processing queue"""
    try:
        queue_dir = get_queue_dir()
        os.makedirs(queue_dir, exist_ok=True)
        
        # Create a queue file with timestamp
        timestamp = int(time.time())
        queue_file = os.path.join(queue_dir, f"{hash_val}_{timestamp}.queue")
        
        with open(queue_file, 'w') as f:
            f.write(f"{hash_val}\n{timestamp}\n")
        
        logger.info(f"Queued torrent {hash_val} for later processing")
        return True
        
    except Exception as e:
        logger.error(f"Failed to queue torrent {hash_val}: {e}")
        return False

def get_queue_status():
    """Get status information about the current queue (optimized for status checks)"""
    try:
        queue_dir = get_queue_dir()
        if not os.path.exists(queue_dir):
            return {'count': 0, 'oldest_timestamp': None, 'items': []}
        
        # For status checks, we only need count and oldest timestamp
        # Don't read file contents unless necessary
        queue_files = [f for f in os.listdir(queue_dir) if f.endswith('.queue')]
        count = len(queue_files)
        
        if count == 0:
            return {'count': 0, 'oldest_timestamp': None, 'items': []}
        
        # Find oldest timestamp from filenames (more efficient than reading files)
        oldest_timestamp = None
        for filename in queue_files:
            try:
                # Extract timestamp from filename: hash_timestamp.queue
                parts = filename.replace('.queue', '').split('_')
                if len(parts) >= 2:
                    timestamp = int(parts[-1])  # Last part should be timestamp
                    if oldest_timestamp is None or timestamp < oldest_timestamp:
                        oldest_timestamp = timestamp
            except (ValueError, IndexError):
                continue
        
        return {
            'count': count,
            'oldest_timestamp': oldest_timestamp,
            'items': []  # Don't populate items for status checks (efficiency)
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {'count': 0, 'oldest_timestamp': None, 'items': []}

def get_queued_torrents():
    """Get list of queued torrents sorted by timestamp (only when actually processing)"""
    try:
        queue_dir = get_queue_dir()
        if not os.path.exists(queue_dir):
            return []
        
        queued_items = []
        
        # Pre-filter files to avoid unnecessary file operations
        queue_files = [f for f in os.listdir(queue_dir) if f.endswith('.queue')]
        
        for filename in queue_files:
            filepath = os.path.join(queue_dir, filename)
            try:
                # Try to extract info from filename first (more efficient)
                parts = filename.replace('.queue', '').split('_')
                if len(parts) >= 2:
                    hash_val = '_'.join(parts[:-1])  # Everything except last part
                    timestamp = int(parts[-1])  # Last part is timestamp
                    
                    # Validate by reading file only if filename parsing succeeded
                    if os.path.exists(filepath):
                        queued_items.append({
                            'hash': hash_val,
                            'timestamp': timestamp,
                            'filepath': filepath
                        })
                else:
                    # Fallback to reading file if filename doesn't match expected format
                    with open(filepath, 'r') as f:
                        lines = f.read().strip().split('\n')
                        if len(lines) >= 2:
                            hash_val = lines[0]
                            timestamp = int(lines[1])
                            queued_items.append({
                                'hash': hash_val,
                                'timestamp': timestamp,
                                'filepath': filepath
                            })
            except Exception as e:
                logger.warning(f"Error reading queue file {filepath}: {e}")
                # Remove corrupted queue file
                try:
                    os.unlink(filepath)
                except:
                    pass
        
        # Sort by timestamp (oldest first)
        return sorted(queued_items, key=lambda x: x['timestamp'])
        
    except Exception as e:
        logger.error(f"Error getting queued torrents: {e}")
        return []

def remove_from_queue(hash_val):
    """Remove a torrent from the processing queue"""
    try:
        queue_dir = get_queue_dir()
        if not os.path.exists(queue_dir):
            return True
        
        # Find and remove queue files for this hash
        removed = False
        for filename in os.listdir(queue_dir):
            if filename.startswith(f"{hash_val}_") and filename.endswith('.queue'):
                filepath = os.path.join(queue_dir, filename)
                try:
                    os.unlink(filepath)
                    logger.debug(f"Removed {hash_val} from queue")
                    removed = True
                except Exception as e:
                    logger.warning(f"Error removing queue file {filepath}: {e}")
        
        return removed
        
    except Exception as e:
        logger.error(f"Error removing {hash_val} from queue: {e}")
        return False

def clear_queue():
    """Clear all items from the processing queue"""
    try:
        queue_dir = get_queue_dir()
        if not os.path.exists(queue_dir):
            logger.info("Queue directory doesn't exist - nothing to clear")
            return True
        
        removed_count = 0
        for filename in os.listdir(queue_dir):
            if filename.endswith('.queue'):
                filepath = os.path.join(queue_dir, filename)
                try:
                    os.unlink(filepath)
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Error removing queue file {filepath}: {e}")
        
        logger.info(f"Cleared {removed_count} item(s) from queue")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing queue: {e}")
        return False

def is_space_management_running():
    """Check if space management is currently running"""
    lock_file = get_lock_file_path('space_management')
    
    # Check if lock file exists
    if not os.path.exists(lock_file):
        return False
    
    # Try to read PID from lock file
    try:
        with open(lock_file, 'r') as f:
            pid_str = f.read().strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                # Check if process is still running
                try:
                    os.kill(pid, 0)  # Signal 0 just checks if process exists
                    return True
                except OSError:
                    # Process doesn't exist, remove stale lock file
                    os.unlink(lock_file)
                    return False
    except Exception as e:
        logger.warning(f"Error checking space management lock: {e}")
    
    return False

# ===================================================================
# Timeout and Retry Utilities
# ===================================================================
@contextmanager
def timeout_context(seconds):
    """Context manager that raises TimeoutError if code takes too long"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Set up signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)  # Cancel alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler

def retry_with_backoff(max_attempts=3, base_delay=1, max_delay=30):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
                        raise
                    
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator

# ===================================================================

# ===================================================================
# Helper Functions
# ===================================================================
def get_available_space_gb(path):
    """Gets available disk space in GB for the given path using shutil."""
    try:
        usage = shutil.disk_usage(path)
        available_gb = usage.free / (1024**3)
        return available_gb
    except FileNotFoundError:
        logger.error(f"Path '{path}' not found for disk usage check.")
        return None
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
        return None

def get_dir_stats(path):
    """Calculates total size (bytes) and item count (files+dirs) for a directory path."""
    total_size = 0; item_count = 1
    if not os.path.isdir(path): return 0, 0
    try:
        for dirpath, dirnames, filenames in os.walk(path, topdown=True, onerror=lambda e: logger.warning(f"os.walk error: {e}")):
            item_count += len(dirnames) + len(filenames)
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try: total_size += os.path.getsize(fp)
                    except OSError as e: logger.warning(f"Could not get size of {fp}: {e}")
    except OSError as e: logger.warning(f"Error walking directory {path}: {e}")
    return total_size, item_count

def cleanup_destination(path):
    """Attempts to remove a file or directory, used for cleaning up failed copies."""
    logger.info(f"Attempting to cleanup possibly incomplete destination: {path}")
    
    # Import config to check DRY_RUN flag
    import config
    
    if config.DRY_RUN:
        if os.path.isdir(path):
            logger.info(f"[DRY RUN] Would remove directory: {path}")
        elif os.path.isfile(path):
            logger.info(f"[DRY RUN] Would remove file: {path}")
        else:
            logger.info(f"[DRY RUN] Path not found, no cleanup needed: {path}")
        return
    
    try:
        if os.path.isdir(path): 
            shutil.rmtree(path)
            logger.info("Cleanup successful (removed directory).")
        elif os.path.isfile(path): 
            os.remove(path)
            logger.info("Cleanup successful (removed file).")
        else: 
            logger.info("Cleanup skipped (path not found).")
    except OSError as e: 
        logger.error(f"Cleanup FAILED: {e}")

@retry_with_backoff(max_attempts=3, base_delay=2)
def get_torrent_info(engine: 'RtorrentEngine', hash_val: BTIH, wait_for_stability=True) -> TorrentInfo:
    """
    Gets and parses torrent information using RtorrentEngine with timeout and retry logic

    param engine: The RtorrentEngine instance to use for fetching torrent data.
    param hash_val: The BTIH hash value of the torrent to fetch info for.
    param wait_for_stability: If True, adds delay to wait for torrent state to stabilize
    return: A TorrentInfo object containing the torrent's name, path, directory, size, is_multi_file status, and label.
    example: TorrentInfo(hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'), name='daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv', path='\\downloading\\sonarr\\daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv', directory='/downloading/sonarr', size=5408683456, is_multi_file=False, label='sonarr')
    """
    logger.debug("Getting torrent info...")
    
    # Add initial delay to let torrent state stabilize if requested
    if wait_for_stability:
        stability_delay = 3  # seconds
        logger.info(f"Waiting {stability_delay}s for torrent state to stabilize...")
        time.sleep(stability_delay)
    
    try:
        with timeout_context(30):  # 30 second timeout for getting torrent info
            info_keys = ["name", "path", "directory", "size", "is_multi_file", "label"]
            sanitized_info_keys = [key for key in info_keys if key in FIELD_REGISTRY]
            prefetch = [
                FIELD_REGISTRY[f].requires
                for f in sanitized_info_keys
            ]
            prefetch = [item for sublist in prefetch for item in sublist]
            
            logger.debug(f"Fetching torrent info for {hash_val} with timeout...")
            item: RtorrentItem = engine.item(hash_val, prefetch)
            
            if item is None:
                logger.error(f"Torrent {hash_val} not found.")
                return None
            
            torrent_info = TorrentInfo(hash_val, *[getattr(item, key, None) for key in info_keys])
            logger.debug(f"Successfully retrieved info for torrent: {torrent_info.name}")
            return torrent_info
            
    except TimeoutError as e:
        logger.error(f"Timeout getting torrent info for {hash_val}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get torrent info for {hash_val}: {e}")
        raise

def get_torrents_by_path(engine: 'RtorrentEngine', path: str, complete=True) -> typing.List['RtorrentItem']:
    """
    Gets a list of torrent hashes that match the given path.

    param engine: The RtorrentEngine instance to use for fetching torrent data.
    param path: The path to search for torrents.
    param complete: If True, only include torrents that are complete.
    return: A list of RtorrentItem for torrents that match the given criteria.
    """
    logger.debug(f"Getting torrents by path: {path}")
    info_keys = ["hash", "name", "path", "directory", "size", "is_multi_file", "label", "completed"]
    sanitized_info_keys = [key for key in info_keys if key in FIELD_REGISTRY]
    # Get key names from the query
    match_string = f"realpath={path}"
    query_tree = matching.QueryGrammar.parse(
            matching.cli_args_to_match_str([match_string])
        )
    key_names = matching.KeyNameVisitor().visit(query_tree)
    matcher = matching.MatcherBuilder().visit(query_tree)
    logger.debug(f"Matcher: {matcher.to_match_string()}")
    prefetch = [
        FIELD_REGISTRY[f].requires
        for f in sanitized_info_keys
        + key_names
    ]
    prefetch = [item for sublist in prefetch for item in sublist]
    logger.debug(f"Prefetch: {set(prefetch)}")
    view = engine.view(matcher=matcher)
    matches = list(engine.items(view=view, prefetch=set(prefetch)))
    logger.debug(f"Found {len(matches)} matches")
    return matches

def verify_copy(src_path, dst_path, is_multi):
    """Verifies copy using size (single file) or size+count (multi-file)."""
    logger.debug("Verifying copy...")
    if not src_path or not dst_path:
        logger.error(f"Verification ERROR: Invalid paths provided - src: '{src_path}', dst: '{dst_path}'")
        return False
    if not os.path.exists(src_path): 
        logger.error(f"Verification ERROR: Source path '{src_path}' disappeared!")
        return False
    if not os.path.exists(dst_path): 
        logger.error(f"Verification ERROR: Destination path '{dst_path}' does not exist!")
        return False
    try:
        if not is_multi: # Single file comparison
            src_size = os.path.getsize(src_path)
            dst_size = os.path.getsize(dst_path)
            logger.debug(f"Source File Size: {src_size}")
            logger.debug(f"Dest File Size  : {dst_size}")
            if src_size == dst_size and src_size >= 0: 
                logger.info("Verification successful (file sizes match).")
                return True
            else: 
                logger.error("Verification FAILED! File sizes mismatch or invalid.")
                return False
        else: # Multi-file directory comparison
            src_size, src_count = get_dir_stats(src_path)
            dst_size, dst_count = get_dir_stats(dst_path)
            logger.debug(f"Source Dir : Size={src_size}, Items={src_count}")
            logger.debug(f"Dest Dir   : Size={dst_size}, Items={dst_count}")
            if src_size == dst_size and src_count == dst_count and src_count > 0 and src_size >= 0: 
                logger.info("Verification successful (total size/item count match).")
                return True
            elif src_size == 0 and dst_size == 0 and src_count == dst_count: 
                logger.info("Verification successful (both source and dest seem empty/zero size).")
                return True
            else: 
                logger.error("Verification FAILED! Size or item count mismatch.")
                return False
    except OSError as e: 
        logger.error(f"Verification ERROR: Could not get stats for paths '{src_path}' or '{dst_path}': {e}")
        return False

# Global cache for process monitoring (avoid frequent expensive scans)
_process_cache = {'data': None, 'timestamp': 0, 'ttl': 5}  # 5 second TTL

def check_running_processes():
    """Check for running pyrosimple-manager child processes (with caching)"""
    import psutil
    import os
    
    # Check cache first
    current_time = time.time()
    if (_process_cache['data'] is not None and 
        current_time - _process_cache['timestamp'] < _process_cache['ttl']):
        logger.debug("Using cached process list")
        return _process_cache['data']
    
    try:
        current_pid = os.getpid()
        child_processes = []
        
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (process.info['name'] and 'python' in process.info['name'].lower() and 
                    process.info['cmdline'] and 
                    any('pyrosimple-manager' in arg for arg in process.info['cmdline']) and
                    any('--child-process' in arg for arg in process.info['cmdline']) and
                    process.info['pid'] != current_pid):
                    
                    child_processes.append({
                        'pid': process.info['pid'],
                        'cmdline': ' '.join(process.info['cmdline'])
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Update cache
        _process_cache['data'] = child_processes
        _process_cache['timestamp'] = current_time
        logger.debug(f"Updated process cache with {len(child_processes)} processes")
        
        return child_processes
    except ImportError:
        logger.warning("psutil not available - cannot check running processes")
        return []
    except Exception as e:
        logger.warning(f"Error checking running processes: {e}")
        return []

def log_process_status():
    """Log current background process status"""
    processes = check_running_processes()
    if processes:
        logger.info(f"Found {len(processes)} running background processes:")
        for proc in processes:
            logger.info(f"  PID {proc['pid']}: {proc['cmdline']}")
    else:
        logger.debug("No background processes currently running")

def invalidate_process_cache():
    """Invalidate the process cache (call when starting/stopping processes)"""
    global _process_cache
    _process_cache['data'] = None
    _process_cache['timestamp'] = 0
    logger.debug("Process cache invalidated")

# ===================================================================

