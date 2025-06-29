# rFlood with Integrated Pyrosimple-Manager

This is an enhanced rFlood container that includes the pyrosimple-manager scripts for automatic torrent management.

## Features

- **Automatic Processing**: When torrents complete, they are automatically copied from SSD to HDD
- **Space Management**: Monitors SSD space and relocates older torrents when needed
- **Arr Integration**: Notifies Sonarr/Radarr after successful copy
- **Health Checks**: Built-in health monitoring for all components
- **Single Container**: Everything runs in one container for simplicity

## Quick Start

### 1. Build the Container

```bash
cd downloads/rflood-next
docker build -t rflood-next:latest .
```

### 2. Set Environment Variables

Create or update your `.env` file:

```env
# Required for Arr integration
SONARR_API_KEY=your-sonarr-api-key-here
RADARR_API_KEY=your-radarr-api-key-here

# Optional configuration
DISK_SPACE_THRESHOLD_GB=100
NOTIFY_ARR_ENABLED=true
```

### 3. Deploy

```bash
cd downloads
docker compose up -d rflood
```

## Configuration

The pyrosimple-manager configuration is stored at `/config/pyrosimple-manager/config.py` inside the container.

You can override settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISK_SPACE_THRESHOLD_GB` | 100 | Free space threshold (GB) |
| `DOWNLOAD_PATH_SSD` | /downloads/flood | SSD cache path |
| `FINAL_DEST_BASE_HDD` | /downloads | HDD storage path |
| `SONARR_API_KEY` | (empty) | Sonarr API key |
| `RADARR_API_KEY` | (empty) | Radarr API key |
| `NOTIFY_ARR_ENABLED` | true | Enable Arr notifications |

## How It Works

1. **Download Completes**: rtorrent triggers the `event.download.finished` event
2. **Process Torrent**: The pyrosimple-manager script:
   - Copies the torrent data from SSD to HDD
   - Verifies the copy succeeded
   - Notifies Sonarr/Radarr (if configured)
3. **Space Management**: Every hour, the script checks SSD space and relocates old torrents if needed

## Monitoring

### Check Health Status

```bash
docker exec rflood python /app/pyrosimple-manager/healthcheck.py
```

### View Logs

```bash
# Container logs
docker logs rflood

# Pyrosimple-manager logs
docker exec rflood tail -f /config/log/pyrosimple-manager.log
```

### Manual Run

```bash
# Process specific torrent
docker exec rflood python /app/pyrosimple-manager/main.py TORRENT_HASH

# Run space check
docker exec rflood python /app/pyrosimple-manager/main.py

# Dry run mode
docker exec rflood python /app/pyrosimple-manager/main.py --dry-run
```

## Directory Structure

Inside the container:
```
/app/
├── rtorrent              # rtorrent binary
├── flood                 # Flood UI
└── pyrosimple-manager/   # Management scripts
    ├── main.py
    ├── core.py
    ├── util.py
    ├── config.py -> /config/pyrosimple-manager/config.py
    └── healthcheck.py

/config/
├── rtorrent.rc          # rtorrent configuration
├── pyrosimple-manager/
│   └── config.py        # Pyrosimple-manager config
└── log/
    └── pyrosimple-manager.log
```

## Troubleshooting

### Torrents not being processed

1. Check if the event handler is configured:
   ```bash
   docker exec rflood grep pyrosimple /config/rtorrent.rc
   ```

2. Check for errors in logs:
   ```bash
   docker exec rflood tail -n 50 /config/log/rtorrent-*.log
   ```

### Sonarr/Radarr not importing

1. Verify API keys are set:
   ```bash
   docker exec rflood env | grep API_KEY
   ```

2. Test connectivity:
   ```bash
   docker exec rflood python -c "import requests; print(requests.get('http://sonarr:8989/api/v3/system/status', headers={'X-Api-Key': 'YOUR_KEY'}).status_code)"
   ```

### Space not being freed

1. Check current space:
   ```bash
   docker exec rflood df -h /downloads
   ```

2. Run space check manually:
   ```bash
   docker exec rflood python /app/pyrosimple-manager/main.py
   ```

## Advanced Usage

### Custom Processing

You can customize the processing by editing the config:

```python
# Increase retry attempts
COPY_RETRY_ATTEMPTS = 5

# Change space threshold
DISK_SPACE_THRESHOLD_GB = 200

# Disable verification (not recommended)
VERIFICATION_ENABLED = False
```

### Integration with Other Services

The script can be called from other services or scripts:

```bash
# From another container
docker exec rflood python /app/pyrosimple-manager/main.py HASH

# Via cron
*/30 * * * * docker exec rflood python /app/pyrosimple-manager/main.py
```

## Development

To modify the scripts:

1. Edit files in `downloads/rflood-next/pyrosimple-manager/`
2. Rebuild the container
3. Test changes

For live development, mount the scripts as a volume:

```yaml
volumes:
  - ./pyrosimple-manager:/app/pyrosimple-manager:ro
``` 