#!/usr/bin/env python3

import sys
import time
import argparse
import core
import config

# Import logging from our logger module
try:
    from logger import setup_logging
    logger = setup_logging('pyrosimple-manager')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('pyrosimple-manager')

# Import required modules
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
        logger.warning("===== DRY RUN MODE - NO CHANGES WILL BE MADE =====")
    logger.info(f"===== Script Execution Started ({time.strftime('%Y-%m-%d %H:%M:%S')}) =====")

    # Validate configuration before proceeding
    try:
        if hasattr(config, 'validate_config'):
            errors, warnings = config.validate_config()
            for warning in warnings:
                logger.warning(warning)
            if errors:
                for error in errors:
                    logger.error(error)
                logger.critical("Configuration errors detected. Exiting.")
                sys.exit(1)
    except Exception as e:
        logger.warning(f"Configuration validation failed: {e}")

    # Initialize pyrosimple engine instance for rtorrent connection
    try:
        logger.info(f"Connecting to rTorrent via SCGI: {config.SCGI_URL}")
        engine = pyrosimple.connect(config.SCGI_URL)
        if engine.rpc is None:
            raise ConnectionError("Failed to connect to rTorrent using pyrosimple engine.")
        logger.info("Successfully connected to rTorrent.")
    except Exception as e:
        logger.critical(f"Failed to connect to rTorrent: {e}")
        sys.exit(1)

    # Check if a torrent hash was passed as a command-line argument
    if args.hash:
        try:
            finished_torrent_hash = BTIH(args.hash)
            logger.info(f"Processing specific torrent: {finished_torrent_hash}")
            # If hash provided, process this specific torrent (Copy/Verify/Notify)
            # Calls the function from core.py
            core.process_single_torrent(engine, finished_torrent_hash)
            
            # Optional: Display torrent info for debugging
            torrent_info = get_torrent_info(engine, finished_torrent_hash)
            if torrent_info:
                logger.info(f"Processed torrent: {torrent_info.name}")
                logger.debug(f"Label: {torrent_info.label}, Size: {torrent_info.size/(1024**3):.2f} GB")
        except ValueError as e:
            logger.error(f"Invalid torrent hash provided: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing torrent {args.hash}: {e}")
            # Don't exit here, still run space management
    else:
        # If no hash provided, log that it's likely triggered by 'inserted_new' or manually
        logger.info("--- Script called without specific hash (likely 'inserted_new' or manual) ---")
        logger.info("--- Skipping Copy/Verify/Notify for specific torrent ---")

    # Always run the space management check function afterwards, handles all relocations
    try:
        logger.info("Running SSD space management check...")
        # Calls the function from core.py
        core.manage_ssd_space(engine)
    except Exception as e:
        logger.error(f"Error during space management: {e}")
        # This is serious but not necessarily fatal

    # Log script end time
    logger.info(f"===== Script Execution Finished ({time.strftime('%Y-%m-%d %H:%M:%S')}) =====")
# ===================================================================
