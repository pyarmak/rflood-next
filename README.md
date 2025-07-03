# rflood-next

A comprehensive Docker container combining rTorrent, Flood UI, and intelligent SSD management for high-performance torrenting with automatic space optimization.

## Overview

rflood-next is an enhanced container that integrates:
- **rTorrent v0.15.5** - High-performance BitTorrent client optimized for private trackers
- **Flood UI v4.9.3** - Modern, responsive web interface  
- **Pyrosimple-Manager** - Intelligent SSD cache management with Arr integration
- **Auto-Migration** - Automatic copy/move from fast SSD to slower HDD storage
- **Smart Monitoring** - Health checks, logging, and performance optimization

## Key Features

### 🚀 **Performance Optimized**
- SSD caching for active downloads with automatic migration
- Private tracker optimizations (disabled DHT/PEX, optimized peer settings)
- Intelligent space management with configurable thresholds
- Comprehensive retry logic and error handling

### 🔄 **Seamless Integration**
- Direct Sonarr/Radarr notifications via API
- Proper timestamp tracking for space management decisions
- Container-native configuration via environment variables
- Health monitoring with startup grace periods

### 🛡️ **Production Ready**
- Comprehensive test coverage for all core functionality
- Structured logging with configurable levels
- Graceful error handling and recovery
- Docker health checks and monitoring

### 📁 **Smart File Management**
- Automatic verification of copy operations
- Safe relocation with path validation
- Configurable retry attempts for reliability
- Support for both single files and multi-file torrents

## Quick Start

### 1. Configure Environment
```bash
# Copy and edit environment file
cp env.example .env
# Set your paths and API keys in .env
```

### 2. Deploy with Docker Compose
```bash
# Build and start
docker compose up -d rflood

# Check health
docker exec rflood python /app/pyrosimple-manager/healthcheck.py
```

### 3. Access Services
- **Flood UI**: `http://your-host:3000` 

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Fast SSD      │───▶│  Pyrosimple      │───▶│   Slow HDD      │
│   (Downloads)   │    │   Manager        │    │  (Completed)    │
│                 │    │                  │    │                 │
│ /downloads/ssd  │    │ • Copy & Verify  │    │ /downloads/hdd  │
│                 │    │ • Space Monitor  │    │                 │
│                 │    │ • Arr Notify     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                        │                       │
         │                        ▼                       │
┌─────────────────┐    ┌──────────────────┐              │
│   rTorrent      │    │  Sonarr/Radarr   │              │
│                 │    │  Integration     │              │
│ • Downloads     │    │                  │              │
│ • Event Hooks   │    │ • API Calls      │◀─────────────┘
│ • Timestamps    │    │ • Auto Import    │
└─────────────────┘    └──────────────────┘
         ▲
         │
┌─────────────────┐
│   Flood UI      │
│                 │
│ • Web Interface │
│ • Management    │
│ • Monitoring    │
└─────────────────┘
```

## Configuration

### Required Environment Variables
```bash
# Storage paths (CRITICAL - must match volume mounts)
DOWNLOAD_PATH_SSD=/downloads/ssd      # Fast storage
FINAL_DEST_BASE_HDD=/downloads/hdd    # Slow storage

# Arr integration
SONARR_API_KEY=your-sonarr-api-key
RADARR_API_KEY=your-radarr-api-key

# Space management  
DISK_SPACE_THRESHOLD_GB=100           # Cleanup threshold in GB
```

### Optional Configuration
```bash
LOG_LEVEL=INFO                        # DEBUG, INFO, WARNING, ERROR
COPY_RETRY_ATTEMPTS=3                 # Retry attempts for failed copies
VERIFICATION_ENABLED=true             # Verify copy integrity
NOTIFY_ARR_ENABLED=true               # Enable Arr notifications
```

## How It Works

1. **Active Downloads**: Torrents download to fast SSD storage (`DOWNLOAD_PATH_SSD`)

2. **Completion Trigger**: When a torrent completes, rTorrent triggers the pyrosimple-manager

3. **Copy & Verify**: Files are copied to permanent HDD storage with integrity verification

4. **Arr Notification**: Sonarr/Radarr are notified for automatic import

5. **Space Management**: Hourly cleanup moves oldest completed torrents from SSD to free space

6. **Relocation**: Torrents are relocated in rTorrent to point to HDD location and SSD data is removed

## Monitoring

### Health Checks
```bash
# Overall system health
docker exec rflood python /app/pyrosimple-manager/healthcheck.py

# Configuration validation  
docker exec rflood python -c "import config; config.show_config_summary()"

# Manual processing test
docker exec rflood python /app/pyrosimple-manager/main.py --dry-run
```

### Logging
```bash
# All container logs
docker logs rflood

# Pyrosimple-manager specific
docker exec rflood tail -f /config/log/pyrosimple-manager.log

# Debug mode
docker exec rflood env LOG_LEVEL=DEBUG python /app/pyrosimple-manager/main.py
```

## Development

### Running Tests
```bash
# Run the comprehensive test suite
docker exec rflood python -m pytest /app/pyrosimple-manager/tests/ -v

# Test specific component
docker exec rflood python -m pytest /app/pyrosimple-manager/tests/test_core.py
```

### Local Development
```bash
# Mount source for live editing
docker run -v ./pyrosimple-manager:/app/pyrosimple-manager:ro rflood-next

# Build development image
docker build -t rflood-next:dev .
```

## Acknowledgements

Built on solid foundations:
- **[hotio/base](https://github.com/hotio/base)** - Container base with s6-overlay
- **[rakshasa/rtorrent](https://github.com/rakshasa/rtorrent)** v0.15.5 - Core BitTorrent client
- **[jesec/flood](https://github.com/jesec/flood)** v4.9.3 - Modern web interface
- **[kannibalox/pyrosimple](https://github.com/kannibalox/pyrosimple)** v2.14.2 - rTorrent automation

## Changes from Base

### Major Improvements
- **Intelligent SSD Management**: Automatic space optimization with configurable thresholds
- **Production Logging**: Structured logging with multiple levels and file output
- **Enhanced Health Checks**: Startup grace periods and comprehensive system validation
- **Container Optimization**: Environment-based configuration and proper service management
- **Comprehensive Testing**: Full test coverage for critical functionality

### Configuration Enhancements
- **Private Tracker Optimization**: Proper DHT/PEX/UDP settings for private trackers
- **Performance Tuning**: Optimized peer limits, memory usage, and network settings
- **Timestamp Tracking**: Proper `tm_completed` and `tm_loaded` field management
- **Event Integration**: Seamless rtorrent event handling for automation

### Operational Features
- **Dry Run Mode**: Test operations without making changes
- **Configuration Validation**: Runtime validation of paths and settings
- **Graceful Error Handling**: Proper error recovery and logging
- **Service Integration**: Direct API integration with Sonarr/Radarr

This container represents a production-ready solution for high-performance torrenting with intelligent storage management, designed for users who need reliability, performance, and automation.