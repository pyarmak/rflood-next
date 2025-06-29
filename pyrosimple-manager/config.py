# ===================================================================
# Configuration File for rTorrent SSD Cache Manager Script
# ===================================================================

# --- Behaviour ---
DISK_SPACE_THRESHOLD_GB = 700            # Free space threshold on SSD (in GB) below which cleanup occurs.
COPY_RETRY_ATTEMPTS = 3                  # Number of times to attempt copy if verification fails (1 = try once, no retries).
VERIFICATION_ENABLED = True              # Verify copy using size/count check? (True/False).
NOTIFY_ARR_ENABLED = True                # Notify Sonarr/Radarr after successful copy/verify? (True/False).

# --- Paths ---
DOWNLOAD_PATH_SSD = "/downloading"      # SSD cache path (rTorrent's working directory).
FINAL_DEST_BASE_HDD = "/downloads/flood" # Base path on HDD for completed data (contains tag subdirectories).

# --- pyrosimple Configuration ---
# SCGI URL for connecting to rTorrent.
# Format: "http(s)://user:pass@host:port/path" or "scgi://host:port" or "/path/to/socket.scgi"
# Example: SCGI_URL = "scgi://192.168.1.119:5000"
# Example: SCGI_URL = "http://user:password@192.168.1.119/RPC2"
SCGI_URL = "http://hotio:qstnbJ57HhUtxA==@192.168.1.119:5000/RPC2?rpc=json" # Replace with your actual URL

# --- Sonarr/Radarr Configuration ---
# Sonarr Details (if used)
SONARR_URL = "http://YOUR_SONARR_IP:8989"  # Replace with your Sonarr instance URL.
SONARR_API_KEY = "YOUR_SONARR_API_KEY"     # Found in Sonarr > Settings > General > Security.
SONARR_TAG = "sonarr"                      # The tag/label assigned to Sonarr downloads in rTorrent (d.custom1).

# Radarr Details (if used)
RADARR_URL = "http://YOUR_RADARR_IP:7878"  # Replace with your Radarr instance URL.
RADARR_API_KEY = "YOUR_RADARR_API_KEY"     # Found in Radarr > Settings > General > Security.
RADARR_TAG = "radarr"                      # The tag/label assigned to Radarr downloads in rTorrent (d.custom1).

# --- (Advanced - Rarely need changing) ---
# PYTHON_INTERPRETER = "/usr/bin/python3" # Path to python3 interpreter (usually not needed directly now)

# ===================================================================
# Derived Configuration (Convenience Dictionary for Arr details)
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

# Runtime flags (set by main.py, not user configuration)
DRY_RUN = False

# ===================================================================

