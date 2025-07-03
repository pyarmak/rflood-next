# ===================================================================
# Container Configuration for rTorrent SSD Cache Manager
# 
# This configuration is designed to work within the rflood container
# ===================================================================

import os

# --- Disk Space Management ---
DISK_SPACE_THRESHOLD_GB = int(os.getenv('DISK_SPACE_THRESHOLD_GB', '100'))

# --- Copy Behavior ---
COPY_RETRY_ATTEMPTS = int(os.getenv('COPY_RETRY_ATTEMPTS', '3'))
VERIFICATION_ENABLED = os.getenv('VERIFICATION_ENABLED', 'true').lower() == 'true'

# --- Notifications ---
NOTIFY_ARR_ENABLED = os.getenv('NOTIFY_ARR_ENABLED', 'true').lower() == 'true'

# --- Storage Paths (Container paths) ---
# These should match the container's volume mounts
# Default to sensible container paths if environment variables are not set
DOWNLOAD_PATH_SSD = os.getenv('DOWNLOAD_PATH_SSD', '/downloads/ssd')
FINAL_DEST_BASE_HDD = os.getenv('FINAL_DEST_BASE_HDD', '/downloads/hdd')

# --- rTorrent Connection (Local SCGI) ---
# Since we're in the same container, use local SCGI socket or localhost
# Allow override for different container networking setups
# SCGI_URL = os.getenv('SCGI_URL', 'scgi://127.0.0.1:5000')
SCGI_URL = os.getenv('SCGI_URL', '/dev/shm/rtorrent.sock')

# --- Sonarr Configuration ---
SONARR_URL = os.getenv('SONARR_URL', 'http://sonarr:8989')
SONARR_API_KEY = os.getenv('SONARR_API_KEY', '')
SONARR_TAG = os.getenv('SONARR_TAG', 'sonarr')

# --- Radarr Configuration ---
RADARR_URL = os.getenv('RADARR_URL', 'http://radarr:7878')
RADARR_API_KEY = os.getenv('RADARR_API_KEY', '')
RADARR_TAG = os.getenv('RADARR_TAG', 'radarr')

# --- Logging Configuration ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', '/config/log/pyrosimple-manager.log')

# ===================================================================
# Derived Configuration
# ===================================================================
ARR_CONFIG = {
    "NOTIFY_ARR_ENABLED": NOTIFY_ARR_ENABLED,
    "SONARR_URL": SONARR_URL,
    "SONARR_API_KEY": SONARR_API_KEY,
    "RADARR_URL": RADARR_URL,
    "RADARR_API_KEY": RADARR_API_KEY,
    "SONARR_TAG": SONARR_TAG,
    "RADARR_TAG": RADARR_TAG
}

# Runtime flags
DRY_RUN = False

# ===================================================================
# Container-specific validation
# ===================================================================
def validate_config():
    """Validate configuration values for container environment"""
    errors = []
    warnings = []
    
    # Check critical environment variables
    if not DOWNLOAD_PATH_SSD or DOWNLOAD_PATH_SSD == '/downloads/ssd':
        warnings.append("DOWNLOAD_PATH_SSD using default value - ensure this matches your volume mounts")
    
    if not FINAL_DEST_BASE_HDD or FINAL_DEST_BASE_HDD == '/downloads/hdd':
        warnings.append("FINAL_DEST_BASE_HDD using default value - ensure this matches your volume mounts")
    
    # Check if API keys are configured for notifications
    if NOTIFY_ARR_ENABLED:
        if not SONARR_API_KEY:
            warnings.append("SONARR_API_KEY not set - Sonarr notifications will fail")
        if not RADARR_API_KEY:
            warnings.append("RADARR_API_KEY not set - Radarr notifications will fail")
    
    # Check threshold values
    if DISK_SPACE_THRESHOLD_GB < 10:
        warnings.append(f"DISK_SPACE_THRESHOLD_GB ({DISK_SPACE_THRESHOLD_GB}) seems very low")
    elif DISK_SPACE_THRESHOLD_GB > 1000:
        warnings.append(f"DISK_SPACE_THRESHOLD_GB ({DISK_SPACE_THRESHOLD_GB}) seems very high")
    
    # Check retry attempts
    if COPY_RETRY_ATTEMPTS < 1:
        errors.append("COPY_RETRY_ATTEMPTS must be at least 1")
    elif COPY_RETRY_ATTEMPTS > 10:
        warnings.append(f"COPY_RETRY_ATTEMPTS ({COPY_RETRY_ATTEMPTS}) seems excessive")
    
    # Check paths exist (at runtime)
    if os.path.exists('/config'):  # Only check if we're actually running in container
        if not os.path.exists(DOWNLOAD_PATH_SSD):
            errors.append(f"DOWNLOAD_PATH_SSD '{DOWNLOAD_PATH_SSD}' does not exist")
        elif not os.access(DOWNLOAD_PATH_SSD, os.W_OK):
            errors.append(f"DOWNLOAD_PATH_SSD '{DOWNLOAD_PATH_SSD}' is not writable")
            
        if not os.path.exists(FINAL_DEST_BASE_HDD):
            errors.append(f"FINAL_DEST_BASE_HDD '{FINAL_DEST_BASE_HDD}' does not exist")
        elif not os.access(FINAL_DEST_BASE_HDD, os.W_OK):
            errors.append(f"FINAL_DEST_BASE_HDD '{FINAL_DEST_BASE_HDD}' is not writable")
    
    # Validate log directory
    log_dir = os.path.dirname(LOG_FILE)
    if os.path.exists('/config') and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            warnings.append(f"Could not create log directory {log_dir}: {e}")
    
    return errors, warnings

# Display configuration info when imported
def show_config_summary():
    """Display a summary of current configuration"""
    print("=== Pyrosimple-Manager Configuration ===")
    print(f"SSD Path: {DOWNLOAD_PATH_SSD}")
    print(f"HDD Path: {FINAL_DEST_BASE_HDD}")
    print(f"Space Threshold: {DISK_SPACE_THRESHOLD_GB} GB")
    print(f"Retry Attempts: {COPY_RETRY_ATTEMPTS}")
    print(f"Verification: {'Enabled' if VERIFICATION_ENABLED else 'Disabled'}")
    print(f"Arr Notifications: {'Enabled' if NOTIFY_ARR_ENABLED else 'Disabled'}")
    print(f"Log Level: {LOG_LEVEL}")
    print("=" * 40)

# Run validation when module is imported (but not during tests)
if __name__ != "__main__" and 'pytest' not in os.environ.get('_', ''):
    errors, warnings = validate_config()
    if errors:
        print("ERROR: Configuration issues detected:")
        for error in errors:
            print(f"  - {error}")
    if warnings:
        print("WARNING: Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")

# =================================================================== 