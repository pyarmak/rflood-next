#!/command/with-contenv /bin/bash

# S6_STAGE2_HOOK - Dynamic Flood Service Control
# This script runs during s6-overlay stage2 initialization and can disable
# the flood service dynamically by controlling its inclusion in the user bundle

echo "[S6_STAGE2_HOOK] Starting dynamic service control..."

# Ensure the user contents.d directory exists
USER_CONTENTS_DIR="/etc/s6-overlay/s6-rc.d/user/contents.d"
SERVICE_FLOOD_FILE="${USER_CONTENTS_DIR}/service-flood"

# Check for environment variable to disable flood service
if [[ "${DISABLE_FLOOD_SERVICE,,}" == "true" ]]; then
    echo "[S6_STAGE2_HOOK] DISABLE_FLOOD_SERVICE is set to true"
    echo "[S6_STAGE2_HOOK] Removing service-flood from user bundle..."
    
    # Remove the service-flood file from user contents.d to exclude it from the bundle
    if [[ -f "${SERVICE_FLOOD_FILE}" ]]; then
        rm -f "${SERVICE_FLOOD_FILE}"
        echo "[S6_STAGE2_HOOK] Removed ${SERVICE_FLOOD_FILE}"
    else
        echo "[S6_STAGE2_HOOK] ${SERVICE_FLOOD_FILE} already doesn't exist"
    fi
    
    echo "[S6_STAGE2_HOOK] Flood service excluded from user bundle"
    
elif [[ "${DISABLE_FLOOD_SERVICE,,}" == "false" ]] || [[ -z "${DISABLE_FLOOD_SERVICE}" ]]; then
    echo "[S6_STAGE2_HOOK] DISABLE_FLOOD_SERVICE is false or unset - flood service will be enabled"
    
    # Create the service-flood file in user contents.d to include it in the bundle
    if [[ ! -f "${SERVICE_FLOOD_FILE}" ]]; then
        echo "[S6_STAGE2_HOOK] Adding service-flood to user bundle..."
        touch "${SERVICE_FLOOD_FILE}"
        echo "[S6_STAGE2_HOOK] Created ${SERVICE_FLOOD_FILE}"
    else
        echo "[S6_STAGE2_HOOK] ${SERVICE_FLOOD_FILE} already exists"
    fi
    
    echo "[S6_STAGE2_HOOK] Flood service included in user bundle"
    
else
    echo "[S6_STAGE2_HOOK] Invalid value for DISABLE_FLOOD_SERVICE: ${DISABLE_FLOOD_SERVICE}"
    echo "[S6_STAGE2_HOOK] Valid values are: true, false, or unset"
fi

# Log the final service states for debugging
echo "[S6_STAGE2_HOOK] Service control completed. Current states:"
if [[ -f "${SERVICE_FLOOD_FILE}" ]]; then
    echo "[S6_STAGE2_HOOK] - Flood service: INCLUDED in user bundle (will start)"
else
    echo "[S6_STAGE2_HOOK] - Flood service: EXCLUDED from user bundle (won't start)"
fi

echo "[S6_STAGE2_HOOK] - rTorrent service: ENABLED (always runs)"

echo "[S6_STAGE2_HOOK] Dynamic service control completed"

# Call the original stage2 hook to ensure base functionality is preserved
if [[ -f "/etc/s6-overlay/init-hook" ]]; then
    echo "[S6_STAGE2_HOOK] Calling original stage2 hook..."
    /etc/s6-overlay/init-hook
    echo "[S6_STAGE2_HOOK] Original stage2 hook completed"
else
    echo "[S6_STAGE2_HOOK] Warning: Original stage2 hook not found at /etc/s6-overlay/init-hook"
fi

echo "[S6_STAGE2_HOOK] All stage2 hooks completed" 