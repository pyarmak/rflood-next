# rFlood with Integrated Pyrosimple-Manager

This is an enhanced rFlood container that includes the pyrosimple-manager scripts for automatic torrent management and SSD space optimization.

## Features

- **Automatic Processing**: When torrents complete, they are automatically copied from SSD to HDD
- **Smart Space Management**: Monitors SSD space and relocates older torrents when needed
- **Arr Integration**: Notifies Sonarr/Radarr after successful copy
- **Health Monitoring**: Built-in health checks with startup grace period
- **Comprehensive Logging**: Structured logging with configurable levels
- **Container Optimized**: Single container solution with proper service management

## Quick Start

### 1. Prepare Environment

Copy the environment template and configure your paths:

```bash
cd downloads
cp env.example .env
# Edit .env with your actual paths and API keys
```

**Critical**: Ensure your volume paths match the environment variables:

```env
# These paths MUST match your actual volume mounts
DOWNLOAD_PATH_SSD=/downloads/ssd    # Fast storage for active downloads
FINAL_DEST_BASE_HDD=/downloads/hdd  # Slow storage for completed files
```

### 2. Build the Container

```bash
cd downloads/rflood-next
docker build -t rflood-next:latest .
```

### 3. Deploy

```bash
cd downloads
docker compose up -d rflood
```

## Configuration

### Environment Variables

All configuration is done via environment variables for container deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| `DOWNLOAD_PATH_SSD` | `/downloads/ssd` | **CRITICAL**: SSD cache path (fast storage) |
| `FINAL_DEST_BASE_HDD` | `/downloads/hdd` | **CRITICAL**: HDD storage path (slow storage) |
| `DISK_SPACE_THRESHOLD_GB` | `100` | Free space threshold (GB) for cleanup |
| `COPY_RETRY_ATTEMPTS` | `3` | Number of copy retry attempts |
| `VERIFICATION_ENABLED` | `true` | Enable copy verification (recommended) |
| `NOTIFY_ARR_ENABLED` | `true` | Enable Arr service notifications |
| `SONARR_API_KEY` | *(empty)* | Sonarr API key for notifications |
| `RADARR_API_KEY` | *(empty)* | Radarr API key for notifications |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Volume Mapping

Your Docker Compose should map volumes like this:

```yaml
volumes:
  - /your/config/path:/config                    # Container config
  - /your/fast/storage:/downloads/ssd           # SSD cache
  - /your/slow/storage:/downloads/hdd           # HDD permanent storage
```

## How It Works

### Processing Flow

1. **Download Starts**: Torrent downloads to SSD cache (`DOWNLOAD_PATH_SSD`)
2. **Download Completes**: rtorrent triggers `event.download.finished` 
3. **Automatic Processing**: Pyrosimple-manager:
   - Sets completion timestamp (`tm_completed`)
   - Copies data from SSD to HDD with verification
   - Notifies Sonarr/Radarr if configured
4. **Space Management**: Hourly check relocates oldest torrents if SSD space is low

### Directory Structure

Inside the container:
```
/app/
├── rtorrent              # rtorrent binary
├── flood                 # Flood UI
└── pyrosimple-manager/   # Management scripts
    ├── main.py           # Main entry point
    ├── core.py           # Core functionality  
    ├── util.py           # Utility functions
    ├── config.py         # Configuration (symlink to /config)
    ├── logger.py         # Logging system
    └── healthcheck.py    # Health monitoring

/config/
├── rtorrent.rc          # rtorrent configuration
├── pyrosimple-manager/
│   └── config.py        # Pyrosimple-manager config
└── log/
    └── pyrosimple-manager.log
```

## Monitoring and Troubleshooting

### Health Status

The container includes comprehensive health monitoring:

```bash
# Check overall health
docker exec rflood python /app/pyrosimple-manager/healthcheck.py

# Check configuration
docker exec rflood python -c "import config; config.show_config_summary()"
```

### View Logs

```bash
# Container logs (includes all services)
docker logs rflood

# Pyrosimple-manager specific logs  
docker exec rflood tail -f /config/log/pyrosimple-manager.log

# Debug level logging
docker exec rflood env LOG_LEVEL=DEBUG python /app/pyrosimple-manager/main.py --dry-run
```

### Manual Operations

```bash
# Process specific torrent
docker exec rflood python /app/pyrosimple-manager/main.py TORRENT_HASH

# Run space management check
docker exec rflood python /app/pyrosimple-manager/main.py

# Test mode (no changes)
docker exec rflood python /app/pyrosimple-manager/main.py --dry-run

# Test Sonarr connectivity
docker exec rflood python -c "
import requests, config
r = requests.get(f'{config.SONARR_URL}/api/v3/system/status', 
                headers={'X-Api-Key': config.SONARR_API_KEY})
print(f'Sonarr: {r.status_code}')"
```

## Common Issues and Solutions

### 🚨 Container Won't Start

**Symptom**: Container exits immediately or fails health checks

**Solutions**:
1. Check environment variables are set correctly
2. Verify volume paths exist and are writable
3. Check logs: `docker logs rflood`

```bash
# Validate configuration
docker run --rm -it rflood-next:latest python -c "
import config
errors, warnings = config.validate_config()
print('Errors:', errors)
print('Warnings:', warnings)"
```

### 🚨 Torrents Not Being Processed

**Symptoms**: Completed torrents remain on SSD, no copying occurs

**Solutions**:
1. Check rtorrent configuration has the event handler:
   ```bash
   docker exec rflood grep pyrosimple /config/rtorrent.rc
   ```

2. Verify timestamps are being set:
   ```bash
   docker exec rflood python -c "
   import pyrosimple, config
   engine = pyrosimple.connect(config.SCGI_URL)
   for item in engine.items():
       print(f'{item.name}: tm_completed={getattr(item, \"tm_completed\", \"MISSING\")}')"
   ```

3. Check for errors in logs:
   ```bash
   docker exec rflood grep ERROR /config/log/pyrosimple-manager.log
   ```

### 🚨 Sonarr/Radarr Not Importing

**Symptoms**: Files copied but Arr services don't import

**Solutions**:
1. Verify API keys are correct:
   ```bash
   docker exec rflood env | grep API_KEY
   ```

2. Test connectivity:
   ```bash
   # Test from container
   docker exec rflood python /app/pyrosimple-manager/healthcheck.py | grep -A5 "Arr Services"
   ```

3. Check Arr service logs for import errors

### 🚨 SSD Space Not Being Freed

**Symptoms**: SSD fills up, torrents not relocated

**Solutions**:
1. Check current space and threshold:
   ```bash
   docker exec rflood df -h /downloads/ssd
   docker exec rflood python -c "import config; print(f'Threshold: {config.DISK_SPACE_THRESHOLD_GB}GB')"
   ```

2. Manual space management:
   ```bash
   docker exec rflood python /app/pyrosimple-manager/main.py
   ```

3. Check for completed torrents with timestamps:
   ```bash
   docker exec rflood python -c "
   import pyrosimple, config
   engine = pyrosimple.connect(config.SCGI_URL)
   completed = [item for item in engine.items() if getattr(item, 'complete', False)]
   print(f'Found {len(completed)} completed torrents')"
   ```

## Advanced Configuration

### Custom Processing Rules

You can customize processing by editing the container configuration:

```bash
# Access the container config
docker exec -it rflood vi /config/pyrosimple-manager/config.py
```

Example customizations:
```python
# Increase retry attempts for unreliable storage
COPY_RETRY_ATTEMPTS = 5

# Lower space threshold for more aggressive cleanup  
DISK_SPACE_THRESHOLD_GB = 50

# Disable verification for speed (not recommended)
VERIFICATION_ENABLED = False
```

### Integration with External Services

The pyrosimple-manager can be called from external scripts:

```bash
# From cron or external scripts
docker exec rflood python /app/pyrosimple-manager/main.py HASH

# Via API integration
curl -X POST your-api/webhook \
  -d "docker exec rflood python /app/pyrosimple-manager/main.py $TORRENT_HASH"
```

### Development and Testing

For development work:

```bash
# Mount scripts as volume for live editing
docker run -v ./pyrosimple-manager:/app/pyrosimple-manager:ro rflood-next

# Run tests
docker exec rflood python -m pytest /app/pyrosimple-manager/tests/

# Enable debug logging
docker exec rflood env LOG_LEVEL=DEBUG python /app/pyrosimple-manager/main.py
```

## Migration from Existing Setups

### From Manual Scripts

If you have existing torrent management scripts:

1. **Backup existing configuration**:
   ```bash
   cp ~/.rtorrent.rc ~/.rtorrent.rc.backup
   ```

2. **Update environment variables** to match your current paths

3. **Test with dry-run mode** before going live:
   ```bash
   docker exec rflood python /app/pyrosimple-manager/main.py --dry-run
   ```

### From Other Containers

When migrating from other rtorrent containers:

1. **Export torrent session** from old container
2. **Copy session files** to new config directory  
3. **Verify path mappings** match your existing setup
4. **Update Arr service** download client settings

## Performance Tuning

### SSD Optimization

- Set `DISK_SPACE_THRESHOLD_GB` to 10-20% of your SSD capacity
- Use fast file systems (ext4, xfs) for SSD cache
- Consider separate SSD partitions for downloads vs system

### Network Optimization  

- Ensure good connectivity between container and Arr services
- Use dedicated networks for internal container communication
- Monitor network latency if services are on different hosts

## Support

For issues and feature requests:

1. **Check logs first**: Enable DEBUG logging and examine output
2. **Validate configuration**: Use built-in validation tools
3. **Test connectivity**: Use health check and manual tests
4. **Review documentation**: This guide covers most common scenarios

The container is designed to be self-diagnosing - most issues will be evident in the logs and health checks. 