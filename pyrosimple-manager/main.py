#!/usr/bin/env python3

import sys
import time
import argparse
import core
import config
import pyrosimple
from util import BTIH, get_torrent_info, get_torrents_by_path

# ===================================================================
# Main Execution Logic
# ===================================================================
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='rTorrent SSD Cache Manager')
    parser.add_argument('hash', nargs='?', help='Torrent hash to process (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Run without making actual changes')
    args = parser.parse_args()
    
    # Set dry-run mode globally
    config.DRY_RUN = args.dry_run
    
    # Log script start time
    if config.DRY_RUN:
        print(f"===== DRY RUN MODE - NO CHANGES WILL BE MADE =====")
    print(f"===== Script Execution Started ({time.strftime('%Y-%m-%d %H:%M:%S')}) =====")

    # Initialize pyrosimple engine instance for rtorrent connection
    print(f"Connecting to rTorrent via SCGI: {config.SCGI_URL}")
    engine = pyrosimple.connect(config.SCGI_URL)
    if engine.rpc is None:
        raise ConnectionError("Failed to connect to rTorrent using pyrosimple engine.")
    print("Successfully connected to rTorrent.")

    # Check if a torrent hash was passed as a command-line argument
    if args.hash:
        finished_torrent_hash = BTIH(args.hash)
        # If hash provided, process this specific torrent (Copy/Verify/Notify)
        # Calls the function from core.py
        core.process_single_torrent(engine, finished_torrent_hash)
        
        # Optional: Display torrent info for debugging
        torrent_info = get_torrent_info(engine, finished_torrent_hash)
        if torrent_info:
            print(f"Processed torrent: {torrent_info.name}")
            print(f"Label: {torrent_info.label}, Size: {torrent_info.size/(1024**3):.2f} GB")
    else:
        # If no hash provided, log that it's likely triggered by 'inserted_new' or manually
        print("--- Script called without specific hash (likely 'inserted_new' or manual) ---")
        print("--- Skipping Copy/Verify/Notify for specific torrent ---")

    # Always run the space management check function afterwards, handles all relocations
    # Calls the function from core.py
    core.manage_ssd_space(engine)

    # Log script end time
    print(f"===== Script Execution Finished ({time.strftime('%Y-%m-%d %H:%M:%S')}) =====")
# ===================================================================
