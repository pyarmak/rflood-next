#!/bin/bash
# Test script for verifying pyrosimple-manager integration in rflood container

set -e

CONTAINER_NAME="rflood"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=== Testing Pyrosimple-Manager Integration ==="
echo

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

# Check if container is running
echo "1. Checking container status..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_result 0 "Container is running"
else
    print_result 1 "Container is not running"
    exit 1
fi

# Check if pyrosimple-manager scripts exist
echo
echo "2. Checking pyrosimple-manager installation..."
docker exec $CONTAINER_NAME test -f /app/pyrosimple-manager/main.py
print_result $? "main.py exists"

docker exec $CONTAINER_NAME test -f /app/pyrosimple-manager/healthcheck.py
print_result $? "healthcheck.py exists"

docker exec $CONTAINER_NAME test -f /config/pyrosimple-manager/config.py
print_result $? "config.py exists"

# Check Python dependencies
echo
echo "3. Testing Python imports..."
docker exec $CONTAINER_NAME python -c "import pyrosimple; print('pyrosimple version:', pyrosimple.__version__)"
print_result $? "pyrosimple module available"

docker exec $CONTAINER_NAME python -c "import requests; print('requests installed')"
print_result $? "requests module available"

# Test config loading
echo
echo "4. Testing configuration..."
docker exec $CONTAINER_NAME python -c "
import sys
sys.path.insert(0, '/app/pyrosimple-manager')
import config
print('Config loaded successfully')
print(f'SSD Path: {config.DOWNLOAD_PATH_SSD}')
print(f'HDD Path: {config.FINAL_DEST_BASE_HDD}')
print(f'Threshold: {config.DISK_SPACE_THRESHOLD_GB} GB')
"
print_result $? "Configuration loads correctly"

# Check rtorrent.rc integration
echo
echo "5. Checking rtorrent.rc integration..."
if docker exec $CONTAINER_NAME grep -q "pyrosimple_process" /config/rtorrent.rc; then
    print_result 0 "Event handler configured in rtorrent.rc"
    docker exec $CONTAINER_NAME grep "pyrosimple" /config/rtorrent.rc | head -2
else
    print_result 1 "Event handler NOT found in rtorrent.rc"
fi

# Run healthcheck
echo
echo "6. Running health check..."
if docker exec $CONTAINER_NAME python /app/pyrosimple-manager/healthcheck.py; then
    print_result 0 "Health check passed"
else
    print_result 1 "Health check failed"
fi

# Test dry-run
echo
echo "7. Testing dry-run mode..."
if docker exec $CONTAINER_NAME python /app/pyrosimple-manager/main.py --dry-run; then
    print_result 0 "Dry-run mode works"
else
    print_result 1 "Dry-run mode failed"
fi

# Check permissions
echo
echo "8. Checking permissions..."
SCRIPT_PERMS=$(docker exec $CONTAINER_NAME stat -c %a /app/pyrosimple-manager/main.py)
if [ "$SCRIPT_PERMS" = "755" ]; then
    print_result 0 "Script permissions correct (755)"
else
    print_result 1 "Script permissions incorrect ($SCRIPT_PERMS)"
fi

# Summary
echo
echo "=== Test Summary ==="
echo "Integration test complete. If all tests passed, the pyrosimple-manager"
echo "is properly integrated into the rflood container and ready to use."
echo
echo "To monitor activity:"
echo "  docker logs -f $CONTAINER_NAME"
echo
echo "To manually process a torrent:"
echo "  docker exec $CONTAINER_NAME python /app/pyrosimple-manager/main.py HASH" 