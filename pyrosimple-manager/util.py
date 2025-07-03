#!/usr/bin/env python3

import os
import re
import shutil
from pyrosimple.torrent.engine import FIELD_REGISTRY
from pyrosimple.util import matching
import typing
from dataclasses import dataclass
if typing.TYPE_CHECKING:
    from pyrosimple.torrent.rtorrent import RtorrentItem
    from pyrosimple.torrent.rtorrent import RtorrentEngine

# ===================================================================
# Helper Classes
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
        print(f"Error: Path '{path}' not found for disk usage check.")
        return None
    except Exception as e:
        print(f"Error getting disk usage for {path}: {e}")
        return None

def get_dir_stats(path):
    """Calculates total size (bytes) and item count (files+dirs) for a directory path."""
    total_size = 0; item_count = 1
    if not os.path.isdir(path): return 0, 0
    try:
        for dirpath, dirnames, filenames in os.walk(path, topdown=True, onerror=lambda e: print(f"Warning: os.walk error: {e}")):
            item_count += len(dirnames) + len(filenames)
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try: total_size += os.path.getsize(fp)
                    except OSError as e: print(f"Warning: Could not get size of {fp}: {e}")
    except OSError as e: print(f"Warning: Error walking directory {path}: {e}")
    return total_size, item_count

def cleanup_destination(path):
    """Attempts to remove a file or directory, used for cleaning up failed copies."""
    print(f"  Attempting to cleanup possibly incomplete destination: {path}")
    
    # Import config to check DRY_RUN flag
    import config
    
    if config.DRY_RUN:
        if os.path.isdir(path):
            print(f"  [DRY RUN] Would remove directory: {path}")
        elif os.path.isfile(path):
            print(f"  [DRY RUN] Would remove file: {path}")
        else:
            print(f"  [DRY RUN] Path not found, no cleanup needed: {path}")
        return
    
    try:
        if os.path.isdir(path): shutil.rmtree(path); print("  Cleanup successful (removed directory).")
        elif os.path.isfile(path): os.remove(path); print("  Cleanup successful (removed file).")
        else: print("  Cleanup skipped (path not found).")
    except OSError as e: print(f"  Cleanup FAILED: {e}")

def get_torrent_info(engine: 'RtorrentEngine', hash_val: BTIH) -> TorrentInfo:
    """
    Gets and parses torrent information using RtorrentEngine

    param engine: The RtorrentEngine instance to use for fetching torrent data.
    param hash_val: The BTIH hash value of the torrent to fetch info for.
    return: A TorrentInfo object containing the torrent's name, path, directory, size, is_multi_file status, and label.
    example: TorrentInfo(hash=BTIH('02E5A8D9F7800A063237F0D37467144360D4B70A'), name='daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv', path='\\downloading\\sonarr\\daredevil.born.again.s01e08.hdr.2160p.web.h265-successfulcrab.mkv', directory='/downloading/sonarr', size=5408683456, is_multi_file=False, label='sonarr')
    """
    print("  Getting torrent info...")
    try:
        info_keys = ["name", "path", "directory", "size", "is_multi_file", "label"]
        sanitized_info_keys = [key for key in info_keys if key in FIELD_REGISTRY]
        prefetch = [
            FIELD_REGISTRY[f].requires
            for f in sanitized_info_keys
        ]
        prefetch = [item for sublist in prefetch for item in sublist]
        item: RtorrentItem = engine.item(hash_val, prefetch)
        if item is None:
            print(f"  ERROR: Torrent {hash_val} not found.")
            return None
        torrent_info = TorrentInfo(hash_val, *[getattr(item, key, None) for key in info_keys])
        return torrent_info
    except Exception as e:
        print(f"  ERROR: Failed to get torrent info for {hash_val}: {e}")
        return None

def get_torrents_by_path(engine: 'RtorrentEngine', path: str, complete=True) -> typing.List['RtorrentItem']:
    """
    Gets a list of torrent hashes that match the given path.

    param engine: The RtorrentEngine instance to use for fetching torrent data.
    param path: The path to search for torrents.
    param complete: If True, only include torrents that are complete.
    return: A list of RtorrentItem for torrents that match the given criteria.
    """
    print(f"  Getting torrents by path: {path}")
    info_keys = ["hash", "name", "path", "directory", "size", "is_multi_file", "label", "completed"]
    sanitized_info_keys = [key for key in info_keys if key in FIELD_REGISTRY]
    # Get key names from the query
    match_string = f"realpath={path}"
    query_tree = matching.QueryGrammar.parse(
            matching.cli_args_to_match_str([match_string])
        )
    key_names = matching.KeyNameVisitor().visit(query_tree)
    matcher = matching.MatcherBuilder().visit(query_tree)
    print(f"  Matcher: {matcher.to_match_string()}")
    prefetch = [
        FIELD_REGISTRY[f].requires
        for f in sanitized_info_keys
        + key_names
    ]
    prefetch = [item for sublist in prefetch for item in sublist]
    print(f"  Prefetch: {set(prefetch)}")
    view = engine.view(matcher=matcher)
    matches = list(engine.items(view=view, prefetch=set(prefetch)))
    print(f"  Found {len(matches)} matches")
    return matches

def verify_copy(src_path, dst_path, is_multi):
    """Verifies copy using size (single file) or size+count (multi-file)."""
    print("  Verifying copy...")
    if not src_path or not dst_path:
        print(f"  Verification ERROR: Invalid paths provided - src: '{src_path}', dst: '{dst_path}'")
        return False
    if not os.path.exists(src_path): print(f"  Verification ERROR: Source path '{src_path}' disappeared!"); return False
    if not os.path.exists(dst_path): print(f"  Verification ERROR: Destination path '{dst_path}' does not exist!"); return False
    try:
        if not is_multi: # Single file comparison
            src_size = os.path.getsize(src_path); dst_size = os.path.getsize(dst_path)
            print(f"    Source File Size: {src_size}"); print(f"    Dest File Size  : {dst_size}")
            if src_size == dst_size and src_size >= 0: print("  Verification successful (file sizes match)."); return True
            else: print("  Verification FAILED! File sizes mismatch or invalid."); return False
        else: # Multi-file directory comparison
            src_size, src_count = get_dir_stats(src_path); dst_size, dst_count = get_dir_stats(dst_path)
            print(f"    Source Dir : Size={src_size}, Items={src_count}"); print(f"    Dest Dir   : Size={dst_size}, Items={dst_count}")
            if src_size == dst_size and src_count == dst_count and src_count > 0 and src_size >= 0: print("  Verification successful (total size/item count match)."); return True
            elif src_size == 0 and dst_size == 0 and src_count == dst_count: print("  Verification successful (both source and dest seem empty/zero size)."); return True
            else: print("  Verification FAILED! Size or item count mismatch."); return False
    except OSError as e: print(f"  Verification ERROR: Could not get stats for paths '{src_path}' or '{dst_path}': {e}"); return False
# ===================================================================

