#!/usr/bin/env python3
"""
Health check script for rtorrent manager.
Returns exit code 0 if healthy, 1 if unhealthy.
"""

import sys
import os
import time
from datetime import datetime, timedelta

try:
    import pyrosimple
    import requests
    import config
except ImportError as e:
    print(f"UNHEALTHY: Missing required import: {e}")
    sys.exit(1)

def check_rtorrent_connection():
    """Check if we can connect to rtorrent"""
    try:
        engine = pyrosimple.connect(config.SCGI_URL)
        if engine.rpc is None:
            return False, "Failed to connect to rTorrent"
        
        # Try a simple RPC call
        engine.rpc.system.pid()
        return True, "rTorrent connection OK"
    except Exception as e:
        return False, f"rTorrent connection failed: {str(e)}"

def check_storage_paths():
    """Check if storage paths exist and are writable"""
    errors = []
    
    # Check SSD path
    if not os.path.exists(config.DOWNLOAD_PATH_SSD):
        errors.append(f"SSD path does not exist: {config.DOWNLOAD_PATH_SSD}")
    elif not os.access(config.DOWNLOAD_PATH_SSD, os.W_OK):
        errors.append(f"SSD path is not writable: {config.DOWNLOAD_PATH_SSD}")
    
    # Check HDD path
    if not os.path.exists(config.FINAL_DEST_BASE_HDD):
        errors.append(f"HDD path does not exist: {config.FINAL_DEST_BASE_HDD}")
    elif not os.access(config.FINAL_DEST_BASE_HDD, os.W_OK):
        errors.append(f"HDD path is not writable: {config.FINAL_DEST_BASE_HDD}")
    
    if errors:
        return False, "; ".join(errors)
    return True, "Storage paths OK"

def check_disk_space():
    """Check if there's reasonable disk space"""
    try:
        import shutil
        
        # Check HDD space (should have at least 10GB free)
        hdd_usage = shutil.disk_usage(config.FINAL_DEST_BASE_HDD)
        hdd_free_gb = hdd_usage.free / (1024**3)
        
        if hdd_free_gb < 10:
            return False, f"HDD has only {hdd_free_gb:.1f}GB free (minimum 10GB recommended)"
        
        return True, f"Disk space OK (HDD: {hdd_free_gb:.1f}GB free)"
    except Exception as e:
        return False, f"Failed to check disk space: {str(e)}"

def check_arr_services():
    """Check Sonarr/Radarr connectivity if enabled"""
    if not config.NOTIFY_ARR_ENABLED:
        return True, "Arr notifications disabled"
    
    errors = []
    
    # Check Sonarr
    if config.SONARR_URL != "http://YOUR_SONARR_IP:8989":
        try:
            response = requests.get(
                f"{config.SONARR_URL}/api/v3/system/status",
                headers={"X-Api-Key": config.SONARR_API_KEY},
                timeout=5
            )
            if response.status_code != 200:
                errors.append(f"Sonarr returned status {response.status_code}")
        except Exception as e:
            errors.append(f"Sonarr connection failed: {str(e)}")
    
    # Check Radarr
    if config.RADARR_URL != "http://YOUR_RADARR_IP:7878":
        try:
            response = requests.get(
                f"{config.RADARR_URL}/api/v3/system/status",
                headers={"X-Api-Key": config.RADARR_API_KEY},
                timeout=5
            )
            if response.status_code != 200:
                errors.append(f"Radarr returned status {response.status_code}")
        except Exception as e:
            errors.append(f"Radarr connection failed: {str(e)}")
    
    if errors:
        return False, "; ".join(errors)
    return True, "Arr services OK"

def check_recent_activity():
    """Check if the script has run recently (optional)"""
    # This would be more useful with database tracking
    # For now, just return OK
    return True, "Activity check OK"

def main():
    """Run all health checks"""
    print(f"Health check started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    checks = [
        ("rTorrent Connection", check_rtorrent_connection),
        ("Storage Paths", check_storage_paths),
        ("Disk Space", check_disk_space),
        ("Arr Services", check_arr_services),
        ("Recent Activity", check_recent_activity),
    ]
    
    all_healthy = True
    
    for check_name, check_func in checks:
        try:
            healthy, message = check_func()
            status = "✓" if healthy else "✗"
            print(f"{status} {check_name}: {message}")
            if not healthy:
                all_healthy = False
        except Exception as e:
            print(f"✗ {check_name}: Unexpected error: {str(e)}")
            all_healthy = False
    
    if all_healthy:
        print("\nStatus: HEALTHY")
        sys.exit(0)
    else:
        print("\nStatus: UNHEALTHY")
        sys.exit(1)

if __name__ == "__main__":
    main() 