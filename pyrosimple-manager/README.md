# rTorrent SSD Cache Manager

A Python script to manage rtorrent downloads by automatically copying completed torrents from SSD cache to HDD storage, with optional Sonarr/Radarr integration.

## Features

- **Automatic Copy & Verify**: Copies completed torrents from SSD to HDD with integrity verification
- **SSD Space Management**: Automatically relocates older torrents when SSD space runs low
- **Arr Integration**: Notifies Sonarr/Radarr after successful copy for automatic import
- **Retry Logic**: Configurable retry attempts for failed copies
- **Safety Checks**: Prevents accidental deletion of data outside the download directory

## Requirements

- Python 3.6+
- pyrosimple (`pip install pyrosimple`)
- rtorrent with XMLRPC/SCGI enabled
- Optional: Sonarr/Radarr for media management

## Installation

1. Clone or download this repository:
   ```bash
   git clone https://github.com/yourusername/pyrosimple-manager.git
   cd pyrosimple-manager
   ```

2. Install dependencies:
   ```bash
   pip install pyrosimple requests
   ```

3. Copy the example configuration:
   ```bash
   cp config_example.py config.py
   ```

4. Edit `config.py` with your settings:
   - Set your rtorrent SCGI connection URL
   - Configure your SSD and HDD paths
   - Set up Sonarr/Radarr API keys if using
   - Adjust space threshold and retry settings

## Configuration

Key configuration options in `config.py`:

```python
# Connection to rtorrent
SCGI_URL = "http://user:pass@192.168.1.100:5000/RPC2?rpc=json"

# Storage paths
DOWNLOAD_PATH_SSD = "/mnt/ssd/downloading"     # Fast SSD cache
FINAL_DEST_BASE_HDD = "/mnt/hdd/downloads"     # Final storage

# Space management
DISK_SPACE_THRESHOLD_GB = 100  # Free up space when SSD has less than this

# Sonarr/Radarr settings (optional)
SONARR_URL = "http://192.168.1.100:8989"
SONARR_API_KEY = "your-api-key-here"
```

## Usage

### Manual execution for all torrents:
```bash
python main.py
```

### Process specific torrent by hash:
```bash
python main.py 1234567890ABCDEF1234567890ABCDEF12345678
```

### Integration with rtorrent

Add to your `.rtorrent.rc`:

```bash
# When download completes, process it
method.set_key = event.download.finished,process_complete,"execute.nothrow=python3,/path/to/main.py,$d.hash="

# Optional: Process new torrents
method.set_key = event.download.inserted_new,process_new,"execute.nothrow=python3,/path/to/main.py"
```

## How It Works

1. **Single Torrent Processing** (when hash provided):
   - Copies completed torrent from SSD to HDD
   - Verifies the copy succeeded (file size/count check)
   - Notifies Sonarr/Radarr if configured
   - Retries on failure (configurable attempts)

2. **Space Management** (always runs):
   - Checks available SSD space
   - If below threshold, finds oldest completed torrents
   - Relocates them to HDD and updates rtorrent paths
   - Frees up space for new downloads

## Directory Structure

```
/mnt/ssd/downloading/          # SSD cache (rtorrent active directory)
├── sonarr/                    # TV shows
│   └── Show.S01E01.mkv
└── radarr/                    # Movies
    └── Movie.2023.mkv

/mnt/hdd/downloads/            # HDD storage (final destination)
├── sonarr/                    # Organized by label
│   └── Show.S01E01.mkv
└── radarr/
    └── Movie.2023.mkv
```

## Troubleshooting

### Connection Issues
- Verify SCGI_URL is correct and rtorrent is accessible
- Check firewall rules if connecting remotely
- Test with: `python -c "import pyrosimple; print(pyrosimple.connect('YOUR_SCGI_URL'))"`

### Permission Errors
- Ensure the script has read/write access to both SSD and HDD paths
- Run with appropriate user or adjust directory permissions

### Verification Failures
- Check if source files are still being written to
- Increase COPY_RETRY_ATTEMPTS if network storage is slow
- Verify sufficient space on destination

### Sonarr/Radarr Not Importing
- Confirm API keys are correct
- Check Sonarr/Radarr logs for import errors
- Ensure download client settings match torrent labels

## Testing

Run the included tests:
```bash
pytest tests/
```

## Safety Features

- Won't delete files outside the configured download directory
- Verifies copies before removing originals
- Handles active torrents gracefully
- Comprehensive error logging

## Contributing

Feel free to submit issues, feature requests, or pull requests!

## License

MIT License - see LICENSE file for details 