#!/bin/bash

# S6_STAGE2_HOOK - Dynamic Flood Service Control
# This script runs during s6-overlay stage2 initialization and can disable
# the flood service dynamically based on environment variables

echo "[S6_STAGE2_HOOK] Starting dynamic service control..."

# Check for environment variable to disable flood service
if [[ "${DISABLE_FLOOD_SERVICE,,}" == "true" ]]; then
    echo "[S6_STAGE2_HOOK] DISABLE_FLOOD_SERVICE is set to true"
    
    # Check if flood service directory exists
    if [[ -d /etc/s6-overlay/s6-rc.d/svc-flood ]]; then
        echo "[S6_STAGE2_HOOK] Disabling flood service..."
        
        # Create a down file to prevent the service from starting
        touch /etc/s6-overlay/s6-rc.d/svc-flood/down
        
        # If the service is already running, stop it
        if s6-rc -v2 -t 10000 -d change svc-flood 2>/dev/null; then
            echo "[S6_STAGE2_HOOK] Stopped running flood service"
        fi
        
        echo "[S6_STAGE2_HOOK] Flood service disabled successfully"
    else
        echo "[S6_STAGE2_HOOK] Warning: flood service directory not found"
    fi
    
elif [[ "${DISABLE_FLOOD_SERVICE,,}" == "false" ]] || [[ -z "${DISABLE_FLOOD_SERVICE}" ]]; then
    echo "[S6_STAGE2_HOOK] DISABLE_FLOOD_SERVICE is false or unset - flood service will remain enabled"
    
    # Ensure the down file is removed if it exists (re-enable service)
    if [[ -f /etc/s6-overlay/s6-rc.d/svc-flood/down ]]; then
        echo "[S6_STAGE2_HOOK] Removing down file to re-enable flood service..."
        rm -f /etc/s6-overlay/s6-rc.d/svc-flood/down
        
        # Start the service if it's not running
        if s6-rc -v2 -u change svc-flood 2>/dev/null; then
            echo "[S6_STAGE2_HOOK] Started flood service"
        fi
    fi
    
else
    echo "[S6_STAGE2_HOOK] Invalid value for DISABLE_FLOOD_SERVICE: ${DISABLE_FLOOD_SERVICE}"
    echo "[S6_STAGE2_HOOK] Valid values are: true, false, or unset"
fi

# Log the final service states for debugging
echo "[S6_STAGE2_HOOK] Service control completed. Current states:"
if [[ -f /etc/s6-overlay/s6-rc.d/svc-flood/down ]]; then
    echo "[S6_STAGE2_HOOK] - Flood service: DISABLED"
else
    echo "[S6_STAGE2_HOOK] - Flood service: ENABLED"
fi

echo "[S6_STAGE2_HOOK] - rTorrent service: ENABLED (always runs)"

echo "[S6_STAGE2_HOOK] Dynamic service control hook completed" 