# ===================================================================
# Configuration File for rTorrent SSD Cache Manager Script
# 
# This is an example configuration file. Copy this to 'config.py'
# and modify the values according to your setup.
# ===================================================================

# --- Disk Space Management ---
DISK_SPACE_THRESHOLD_GB = 700            # Free space threshold on SSD (in GB) below which cleanup occurs.
                                        # When SSD free space drops below this, older torrents are relocated.
                                        # Recommendation: Set to 10-20% of your SSD capacity

# --- Copy Behavior ---
COPY_RETRY_ATTEMPTS = 3                  # Number of times to attempt copy if verification fails.
                                        # Set to 1 for no retries, higher for unreliable storage
VERIFICATION_ENABLED = True              # Verify copy using size/count check? (True/False).
                                        # Highly recommended to leave as True

# --- Notifications ---
NOTIFY_ARR_ENABLED = True                # Notify Sonarr/Radarr after successful copy/verify? (True/False).
                                        # Set to False if not using Sonarr/Radarr

# --- Storage Paths ---
# IMPORTANT: Use forward slashes (/) even on Windows, or escape backslashes (\\)
DOWNLOAD_PATH_SSD = "/downloading"       # SSD cache path (rTorrent's working directory).
                                        # This should match your rtorrent download directory
FINAL_DEST_BASE_HDD = "/downloads/flood" # Base path on HDD for completed data.
                                        # Subdirectories will be created based on labels (sonarr/radarr)

# --- rTorrent Connection ---
# pyrosimple SCGI URL for connecting to rTorrent.
# Format options:
#   - "scgi://host:port" - Direct SCGI connection
#   - "http(s)://user:pass@host:port/path" - HTTP/HTTPS with authentication
#   - "/path/to/socket.scgi" - Unix socket
#
# Examples:
#   SCGI_URL = "scgi://192.168.1.119:5000"
#   SCGI_URL = "http://user:password@192.168.1.119/RPC2"
#   SCGI_URL = "https://user:pass@rtorrent.example.com:443/RPC2?rpc=json"
#   SCGI_URL = "/dev/shm/rtorrent.sock"
#
SCGI_URL = "/dev/shm/rtorrent.sock"

# --- Sonarr Configuration ---
# Leave these as defaults if not using Sonarr
SONARR_URL = "http://YOUR_SONARR_IP:8989"  # Replace with your Sonarr instance URL.
                                            # Example: "http://192.168.1.100:8989"
SONARR_API_KEY = "YOUR_SONARR_API_KEY"     # Found in Sonarr > Settings > General > Security.
                                            # 32-character alphanumeric string
SONARR_TAG = "sonarr"                       # The tag/label assigned to Sonarr downloads in rTorrent.
                                            # This should match your Sonarr download client settings

# --- Radarr Configuration ---
# Leave these as defaults if not using Radarr
RADARR_URL = "http://YOUR_RADARR_IP:7878"  # Replace with your Radarr instance URL.
                                            # Example: "http://192.168.1.100:7878"
RADARR_API_KEY = "YOUR_RADARR_API_KEY"     # Found in Radarr > Settings > General > Security.
                                            # 32-character alphanumeric string
RADARR_TAG = "radarr"                       # The tag/label assigned to Radarr downloads in rTorrent.
                                            # This should match your Radarr download client settings

# --- Logging Configuration (Optional) ---
# LOG_LEVEL = "INFO"                        # Options: DEBUG, INFO, WARNING, ERROR
# LOG_FILE = "/var/log/rtorrent-manager.log" # Path to log file, or None for console only

# --- Advanced Options ---
# These rarely need changing
# PYTHON_INTERPRETER = "/usr/bin/python3"   # Path to python3 interpreter
# CONNECTION_TIMEOUT = 30                   # Timeout for rTorrent connections (seconds)
# VERIFY_TIMEOUT = 300                      # Timeout for file verification (seconds)

# ===================================================================
# Derived Configuration (Do not modify)
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

# ===================================================================
# Validation (Optional but recommended)
# ===================================================================
def validate_config():
    """Validate configuration values"""
    errors = []
    
    # Check paths exist
    if not DOWNLOAD_PATH_SSD.startswith(('/','\\', 'C:', 'D:', 'E:')):
        errors.append(f"DOWNLOAD_PATH_SSD '{DOWNLOAD_PATH_SSD}' doesn't look like a valid path")
    
    # Check threshold is reasonable
    if DISK_SPACE_THRESHOLD_GB < 10:
        errors.append(f"DISK_SPACE_THRESHOLD_GB ({DISK_SPACE_THRESHOLD_GB}) seems too low")
    
    # Check SCGI URL format
    if not any(SCGI_URL.startswith(p) for p in ['http://', 'https://', 'scgi://', '/']):
        errors.append(f"SCGI_URL '{SCGI_URL}' doesn't match expected format")
    
    # Check Arr configuration if enabled
    if NOTIFY_ARR_ENABLED:
        if SONARR_URL == "http://YOUR_SONARR_IP:8989":
            errors.append("SONARR_URL not configured but NOTIFY_ARR_ENABLED is True")
        if RADARR_URL == "http://YOUR_RADARR_IP:7878":
            errors.append("RADARR_URL not configured but NOTIFY_ARR_ENABLED is True")
    
    return errors

# Run validation when module is imported
if __name__ != "__main__":
    config_errors = validate_config()
    if config_errors:
        print("WARNING: Configuration issues detected:")
        for error in config_errors:
            print(f"  - {error}")
# =================================================================== 