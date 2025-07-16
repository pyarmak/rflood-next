#!/usr/bin/env python3
"""
Health check script for rtorrent manager.
Returns exit code 0 if healthy, 1 if unhealthy.
"""

import sys
import os
import time
from datetime import datetime

# Check if we're running during container startup
startup_grace_period = 180  # 3 minutes
container_start_file = '/tmp/container_started'

def is_startup_period():
    """Check if we're still in the startup grace period"""
    if not os.path.exists(container_start_file):
        # Create the file if it doesn't exist (first run)
        try:
            with open(container_start_file, 'w') as f:
                f.write(str(time.time()))
            return True
        except:
            return True
    
    try:
        with open(container_start_file, 'r') as f:
            start_time = float(f.read().strip())
        return (time.time() - start_time) < startup_grace_period
    except:
        return True

try:
    import requests
    import config
except ImportError as e:
    print(f"UNHEALTHY: Missing required import: {e}")
    if is_startup_period():
        print("INFO: Still in startup grace period, treating as healthy")
        sys.exit(0)
    sys.exit(1)

def check_flood_ui():
    """Check if Flood UI is accessible and responsive"""
    try:
        # Check if Flood UI is accessible (typically runs on port 3000)
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            return True, "Flood UI accessible"
        else:
            return False, f"Flood UI returned status {response.status_code}"
    except Exception as e:
        return False, f"Flood UI check failed: {str(e)}"

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
        
        # Check SSD space
        ssd_usage = shutil.disk_usage(config.DOWNLOAD_PATH_SSD)
        ssd_free_gb = ssd_usage.free / (1024**3)
        
        # Check HDD space (should have at least 10GB free)
        hdd_usage = shutil.disk_usage(config.FINAL_DEST_BASE_HDD)
        hdd_free_gb = hdd_usage.free / (1024**3)
        
        warnings = []
        if ssd_free_gb < config.DISK_SPACE_THRESHOLD_GB:
            warnings.append(f"SSD below threshold ({ssd_free_gb:.1f}GB < {config.DISK_SPACE_THRESHOLD_GB}GB)")
        if hdd_free_gb < 10:
            warnings.append(f"HDD critically low ({hdd_free_gb:.1f}GB < 10GB)")
        
        if warnings:
            return True, f"Disk space WARNING: {'; '.join(warnings)}"
        
        return True, f"Disk space OK (SSD: {ssd_free_gb:.1f}GB, HDD: {hdd_free_gb:.1f}GB)"
    except Exception as e:
        return False, f"Failed to check disk space: {str(e)}"

def check_arr_services():
    """Check Sonarr/Radarr connectivity if enabled"""
    if not config.NOTIFY_ARR_ENABLED:
        return True, "Arr notifications disabled"
    
    errors = []
    successes = []
    
    # Check Sonarr if configured
    if config.SONARR_API_KEY and config.SONARR_URL != "http://YOUR_SONARR_IP:8989":
        try:
            response = requests.get(
                f"{config.SONARR_URL}/api/v3/system/status",
                headers={"X-Api-Key": config.SONARR_API_KEY},
                timeout=5
            )
            if response.status_code == 200:
                successes.append("Sonarr OK")
            else:
                errors.append(f"Sonarr returned status {response.status_code}")
        except Exception as e:
            errors.append(f"Sonarr connection failed: {str(e)}")
    
    # Check Radarr if configured
    if config.RADARR_API_KEY and config.RADARR_URL != "http://YOUR_RADARR_IP:7878":
        try:
            response = requests.get(
                f"{config.RADARR_URL}/api/v3/system/status",
                headers={"X-Api-Key": config.RADARR_API_KEY},
                timeout=5
            )
            if response.status_code == 200:
                successes.append("Radarr OK")
            else:
                errors.append(f"Radarr returned status {response.status_code}")
        except Exception as e:
            errors.append(f"Radarr connection failed: {str(e)}")
    
    if errors and not successes:
        return False, "; ".join(errors)
    elif errors:
        return True, f"Partial success: {'; '.join(successes)} | Issues: {'; '.join(errors)}"
    elif successes:
        return True, "; ".join(successes)
    else:
        return True, "No Arr services configured"

def check_configuration():
    """Check if configuration is valid"""
    try:
        if hasattr(config, 'validate_config'):
            errors, warnings = config.validate_config()
            if errors:
                return False, f"Configuration errors: {'; '.join(errors)}"
            elif warnings:
                return True, f"Configuration OK (warnings: {len(warnings)})"
            else:
                return True, "Configuration OK"
        else:
            return True, "Configuration validation not available"
    except Exception as e:
        return False, f"Configuration check failed: {str(e)}"

def main():
    """Run all health checks"""
    startup_mode = is_startup_period()
    
    print(f"Health check started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if startup_mode:
        print("INFO: Running in startup grace period mode")
    
    checks = [
        ("Configuration", check_configuration),
        ("Storage Paths", check_storage_paths),
        ("Disk Space", check_disk_space),
        ("Flood UI", check_flood_ui),
        ("Arr Services", check_arr_services),
    ]
    
    all_healthy = True
    critical_failure = False
    
    for check_name, check_func in checks:
        try:
            healthy, message = check_func()
            status = "✓" if healthy else "✗"
            print(f"{status} {check_name}: {message}")
            
            if not healthy:
                all_healthy = False
                # During startup, only configuration and storage paths are critical
                if startup_mode:
                    if check_name in ["Configuration", "Storage Paths"]:
                        critical_failure = True
                else:
                    # After startup, Flood UI is also critical
                    if check_name in ["Configuration", "Storage Paths", "Flood UI"]:
                        critical_failure = True
                        
        except Exception as e:
            print(f"✗ {check_name}: Unexpected error: {str(e)}")
            all_healthy = False
            if not startup_mode or check_name in ["Configuration", "Storage Paths"]:
                critical_failure = True
    
    # Determine final status
    if critical_failure:
        print("\nStatus: UNHEALTHY (critical failure)")
        sys.exit(1)
    elif startup_mode and not all_healthy:
        print("\nStatus: HEALTHY (startup grace period)")
        sys.exit(0)
    elif all_healthy:
        print("\nStatus: HEALTHY")
        sys.exit(0)
    else:
        print("\nStatus: DEGRADED (non-critical issues)")
        sys.exit(0)  # Still report healthy for non-critical issues

if __name__ == "__main__":
    main() 