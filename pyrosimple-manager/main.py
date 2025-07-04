#!/usr/bin/env python3

import sys
import time
import argparse
import subprocess
import os
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
from util import (
    BTIH, log_process_status, check_running_processes, is_space_management_running,
    queue_torrent_for_processing, get_queued_torrents, remove_from_queue, get_queue_status, clear_queue,
    invalidate_process_cache
)

def process_torrent_background(hash_val):
    """Process a single torrent in the background (called as child process)"""
    child_logger = None
    try:
        # Re-setup logging for child process
        child_logger = setup_logging('pyrosimple-manager-child')
        child_logger.info(f"=== Child Process Started for {hash_val} ===")
        
        # Connect to rTorrent in child process
        child_logger.info(f"Child: Connecting to rTorrent via SCGI: {config.SCGI_URL}")
        engine = pyrosimple.connect(config.SCGI_URL)
        if engine.rpc is None:
            raise ConnectionError("Child: Failed to connect to rTorrent using pyrosimple engine.")
        child_logger.info("Child: Successfully connected to rTorrent.")
        
        # Process the torrent
        core.process_single_torrent(engine, BTIH(hash_val))
        
        child_logger.info(f"=== Child Process Completed for {hash_val} ===")
        
    except Exception as e:
        error_msg = f"Child process error for {hash_val}: {e}"
        if child_logger:
            child_logger.error(error_msg)
        else:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)

def space_management_background():
    """Run space management in the background (called as child process)"""
    child_logger = None
    try:
        # Re-setup logging for child process
        child_logger = setup_logging('pyrosimple-manager-space')
        child_logger.info("=== Space Management Child Process Started ===")
        
        # Connect to rTorrent in child process
        child_logger.info(f"Space Child: Connecting to rTorrent via SCGI: {config.SCGI_URL}")
        engine = pyrosimple.connect(config.SCGI_URL)
        if engine.rpc is None:
            raise ConnectionError("Space Child: Failed to connect to rTorrent using pyrosimple engine.")
        child_logger.info("Space Child: Successfully connected to rTorrent.")
        
        # Check if queue processing is needed (avoid unnecessary work)
        queue_status = get_queue_status()
        if queue_status['count'] > 0:
            child_logger.info(f"Found {queue_status['count']} torrent(s) in queue - processing first")
            process_queued_torrents(child_logger)
        else:
            child_logger.debug("Queue is empty - skipping queue processing")
        
        # Then run space management (with locking)
        core.manage_ssd_space(engine)
        
        child_logger.info("=== Space Management Child Process Completed ===")
        
    except Exception as e:
        error_msg = f"Space management child process error: {e}"
        if child_logger:
            child_logger.error(error_msg)
        else:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)

def process_queued_torrents(logger_instance=None):
    """Process any torrents waiting in the queue"""
    if logger_instance is None:
        logger_instance = logger
    
    try:
        queued_items = get_queued_torrents()
        if not queued_items:
            logger_instance.debug("No torrents in queue to process")
            return
        
        logger_instance.info(f"Found {len(queued_items)} torrent(s) in queue - attempting to process...")
        
        for item in queued_items:
            hash_val = item['hash']
            
            # Check if we can start a new process
            running_processes = check_running_processes()
            if len(running_processes) >= config.MAX_CONCURRENT_PROCESSES:
                logger_instance.info(f"Still at process limit ({len(running_processes)}/{config.MAX_CONCURRENT_PROCESSES}) - leaving remaining items in queue")
                break
            
            logger_instance.info(f"Processing queued torrent: {hash_val}")
            
            try:
                # Build command for child process
                script_path = os.path.abspath(__file__)
                cmd = [sys.executable, script_path, '--child-process', '--child-hash', str(hash_val)]
                
                if config.DRY_RUN:
                    cmd.append('--dry-run')
                
                # Spawn child process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                # Only remove from queue AFTER successful process spawn
                remove_from_queue(hash_val)
                
                # Invalidate process cache since we started a new process
                invalidate_process_cache()
                
                logger_instance.info(f"Started background process for queued torrent {hash_val} (PID: {process.pid})")
                
                # Small delay to prevent overwhelming the system
                time.sleep(1)
                
            except Exception as e:
                logger_instance.error(f"Failed to start process for queued torrent {hash_val}: {e}")
                # Keep item in queue since process spawn failed
                logger_instance.info(f"Keeping {hash_val} in queue due to process spawn failure")
    
    except Exception as e:
        logger_instance.error(f"Error processing queued torrents: {e}")

# ===================================================================
# Main Execution Logic
# ===================================================================
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='rTorrent SSD Cache Manager with intelligent queueing',
        epilog='''
Examples:
  %(prog)s HASH                    # Process specific torrent (queue if at limit)
  %(prog)s                        # Run space management and process queue
  %(prog)s --status               # Show background processes and queue status
  %(prog)s --process-queue        # Manually process queued torrents
  %(prog)s --clear-queue          # Clear all queued torrents
  %(prog)s --dry-run HASH         # Test mode - no actual changes
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('hash', nargs='?', help='Torrent hash to process (will queue if at process limit)')
    parser.add_argument('--dry-run', action='store_true', help='Run without making actual changes')
    parser.add_argument('--child-process', action='store_true', help=argparse.SUPPRESS)  # Hide internal flag
    parser.add_argument('--child-hash', help=argparse.SUPPRESS)  # Hide internal flag
    parser.add_argument('--space-management', action='store_true', help=argparse.SUPPRESS)  # Hide internal flag
    parser.add_argument('--status', action='store_true', help='Show status of background processes and queue')
    parser.add_argument('--process-queue', action='store_true', help='Manually process queued torrents')
    parser.add_argument('--clear-queue', action='store_true', help='Clear all queued torrents (emergency use)')
    args = parser.parse_args()
    
    # Set dry-run mode globally
    config.DRY_RUN = args.dry_run
    
    # Validate argument combinations (prevent conflicting options)
    exclusive_actions = [args.status, args.clear_queue, args.process_queue, 
                        args.child_process, args.space_management, bool(args.hash)]
    active_actions = sum(1 for action in exclusive_actions if action)
    
    if active_actions > 1:
        logger.error("Multiple conflicting actions specified. Use only one at a time.")
        sys.exit(1)
    
    # Validate hash early if provided
    if args.hash:
        try:
            BTIH(args.hash)  # This will raise ValueError if invalid
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid torrent hash provided: {e}")
            sys.exit(1)
    
    # Handle status check mode
    if args.status:
        print("Checking background process status...")
        log_process_status()
        
        # Also check space management status
        if is_space_management_running():
            print("Space management process is currently running")
        else:
            print("No space management process currently running")
        
        # Show queue status
        queue_status = get_queue_status()
        if queue_status['count'] > 0:
            print(f"\nQueue status: {queue_status['count']} torrent(s) waiting for processing")
            
            # Get detailed queue info only for display (more efficient)
            queued_items = get_queued_torrents()
            for item in queued_items[:5]:  # Show first 5
                age_minutes = (time.time() - item['timestamp']) / 60
                print(f"  - {item['hash']} (queued {age_minutes:.1f} minutes ago)")
            if len(queued_items) > 5:
                print(f"  ... and {len(queued_items) - 5} more")
        else:
            print("\nQueue status: No torrents waiting in queue")
        
        sys.exit(0)
    
    # Handle queue clearing
    if args.clear_queue:
        logger.info("Queue clearing requested...")
        queue_status = get_queue_status()
        if queue_status['count'] > 0:
            logger.info(f"Clearing {queue_status['count']} item(s) from queue...")
            if clear_queue():
                logger.info("Queue cleared successfully.")
            else:
                logger.error("Failed to clear queue.")
                sys.exit(1)
        else:
            logger.info("Queue is already empty.")
        sys.exit(0)
    
    # Handle manual queue processing
    if args.process_queue:
        logger.info("Manual queue processing requested...")
        
        # Check if queue is empty first (avoid unnecessary work)
        queue_status = get_queue_status()
        if queue_status['count'] == 0:
            logger.info("Queue is empty - nothing to process")
            sys.exit(0)
        
        logger.info(f"Processing {queue_status['count']} queued torrent(s)...")
        process_queued_torrents()
        logger.info("Manual queue processing completed.")
        sys.exit(0)
    
    # Handle child process mode (internal use only)
    if args.child_process and args.child_hash:
        process_torrent_background(args.child_hash)
        sys.exit(0)
    
    # Handle space management child process mode (internal use only)
    if args.space_management:
        space_management_background()
        sys.exit(0)
    
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
    
    # Check if a torrent hash was passed as a command-line argument
    if args.hash:
        try:
            finished_torrent_hash = BTIH(args.hash)
            
            # Check for existing background processes
            running_processes = check_running_processes()
            max_concurrent = config.MAX_CONCURRENT_PROCESSES
            
            if len(running_processes) >= max_concurrent:
                logger.warning(f"Already {len(running_processes)} background processes running (max: {max_concurrent})")
                logger.info(f"Queueing torrent {finished_torrent_hash} for later processing...")
                
                if queue_torrent_for_processing(finished_torrent_hash):
                    logger.info(f"Successfully queued torrent {finished_torrent_hash}")
                    
                    # Show current queue status
                    queue_status = get_queue_status()
                    logger.info(f"Current queue size: {queue_status['count']} torrent(s)")
                else:
                    logger.error(f"Failed to queue torrent {finished_torrent_hash}")
                    sys.exit(1)
                
                sys.exit(0)
            
            logger.info(f"Spawning background process for torrent: {finished_torrent_hash}")
            if running_processes:
                logger.info(f"Current background processes: {len(running_processes)}")
            
            # Build command for child process
            script_path = os.path.abspath(__file__)
            cmd = [sys.executable, script_path, '--child-process', '--child-hash', str(finished_torrent_hash)]
            
            if args.dry_run:
                cmd.append('--dry-run')
            
            # Spawn child process and detach it
            logger.info("Starting background process...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,  # Redirect output to avoid blocking
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent session
            )
            
            # Invalidate process cache since we started a new process
            invalidate_process_cache()
            
            logger.info(f"Background process started with PID: {process.pid}")
            logger.info(f"Main script returning immediately to prevent rTorrent blocking")
            
        except ValueError as e:
            logger.error(f"Invalid torrent hash provided: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error spawning background process for torrent {args.hash}: {e}")
            sys.exit(1)
    else:
        logger.info("--- Script called without specific hash ---")
        
        # Check if space management is already running
        if is_space_management_running():
            logger.info("Space management already running in another process - skipping")
        else:
            # Show queue status before starting space management
            queue_status = get_queue_status()
            if queue_status['count'] > 0:
                logger.info(f"Found {queue_status['count']} torrent(s) in queue - space management will process them first")
            
            logger.info("Spawning background process for space management and queue processing...")
            
            # Build command for space management child process
            script_path = os.path.abspath(__file__)
            cmd = [sys.executable, script_path, '--space-management']
            
            if args.dry_run:
                cmd.append('--dry-run')
            
            try:
                # Spawn child process and detach it
                logger.info("Starting space management background process...")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,  # Redirect output to avoid blocking
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Detach from parent session
                )
                
                # Invalidate process cache since we started a new process
                invalidate_process_cache()
                
                logger.info(f"Space management background process started with PID: {process.pid}")
                logger.info(f"Main script returning immediately to prevent rTorrent blocking")
                
            except Exception as e:
                logger.error(f"Error spawning space management background process: {e}")

    # Log script end time
    logger.info(f"===== Script Execution Finished ({time.strftime('%Y-%m-%d %H:%M:%S')}) =====")
# ===================================================================
