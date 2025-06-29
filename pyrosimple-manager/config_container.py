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
# These match the container's volume mounts
DOWNLOAD_PATH_SSD = os.getenv('DOWNLOAD_PATH_SSD', '/downloads/flood')
FINAL_DEST_BASE_HDD = os.getenv('FINAL_DEST_BASE_HDD', '/downloads')

# --- rTorrent Connection (Local SCGI) ---
# Since we're in the same container, use local SCGI socket or localhost
SCGI_URL = os.getenv('SCGI_URL', 'scgi://127.0.0.1:5000')

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
    
    # Check if API keys are configured
    if NOTIFY_ARR_ENABLED:
        if not SONARR_API_KEY:
            warnings.append("SONARR_API_KEY not set - Sonarr notifications will fail")
        if not RADARR_API_KEY:
            warnings.append("RADARR_API_KEY not set - Radarr notifications will fail")
    
    # Check paths exist
    import os
    if not os.path.exists(DOWNLOAD_PATH_SSD):
        errors.append(f"DOWNLOAD_PATH_SSD '{DOWNLOAD_PATH_SSD}' does not exist")
    if not os.path.exists(FINAL_DEST_BASE_HDD):
        errors.append(f"FINAL_DEST_BASE_HDD '{FINAL_DEST_BASE_HDD}' does not exist")
    
    return errors, warnings

# Run validation
if __name__ != "__main__":
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