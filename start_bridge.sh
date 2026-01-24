#!/bin/bash
# WinWing Bridge Launcher
# Starts the bridge in daemon mode for use with opentrack-launcher or other scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SCRIPT="$SCRIPT_DIR/winwing_bridge.py"
PID_FILE="$SCRIPT_DIR/.bridge.pid"
LOG_FILE="$SCRIPT_DIR/bridge.log"

start_bridge() {
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "Bridge already running (PID: $OLD_PID)"
            return 0
        else
            # Stale PID file
            rm "$PID_FILE"
        fi
    fi

    echo "Starting WinWing Bridge..."

    # Start bridge in background
    python3 "$BRIDGE_SCRIPT" --daemon >> "$LOG_FILE" 2>&1 &
    BRIDGE_PID=$!

    # Save PID
    echo $BRIDGE_PID > "$PID_FILE"

    # Wait a moment and check if it started
    sleep 1
    if ps -p $BRIDGE_PID > /dev/null 2>&1; then
        echo "✓ Bridge started (PID: $BRIDGE_PID)"
        echo "  Log: $LOG_FILE"
        return 0
    else
        echo "✗ Bridge failed to start"
        echo "  Check log: $LOG_FILE"
        rm "$PID_FILE"
        return 1
    fi
}

stop_bridge() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Bridge not running (no PID file)"
        return 0
    fi

    BRIDGE_PID=$(cat "$PID_FILE")

    if ! ps -p "$BRIDGE_PID" > /dev/null 2>&1; then
        echo "Bridge not running (stale PID)"
        rm "$PID_FILE"
        return 0
    fi

    echo "Stopping WinWing Bridge (PID: $BRIDGE_PID)..."
    kill -TERM "$BRIDGE_PID"

    # Wait for clean shutdown
    for i in {1..10}; do
        if ! ps -p "$BRIDGE_PID" > /dev/null 2>&1; then
            echo "✓ Bridge stopped"
            rm "$PID_FILE"
            return 0
        fi
        sleep 0.5
    done

    # Force kill if still running
    echo "Force killing bridge..."
    kill -KILL "$BRIDGE_PID" 2>/dev/null
    rm "$PID_FILE"
    return 0
}

status_bridge() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Bridge: NOT RUNNING"
        return 1
    fi

    BRIDGE_PID=$(cat "$PID_FILE")

    if ps -p "$BRIDGE_PID" > /dev/null 2>&1; then
        echo "Bridge: RUNNING (PID: $BRIDGE_PID)"

        # Show last few log lines
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "Recent activity:"
            tail -n 5 "$LOG_FILE" | sed 's/^/  /'
        fi
        return 0
    else
        echo "Bridge: NOT RUNNING (stale PID)"
        rm "$PID_FILE"
        return 1
    fi
}

restart_bridge() {
    stop_bridge
    sleep 1
    start_bridge
}

# Parse command
case "${1:-start}" in
    start)
        start_bridge
        ;;
    stop)
        stop_bridge
        ;;
    restart)
        restart_bridge
        ;;
    status)
        status_bridge
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "No log file found"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "  start    - Start the bridge in background"
        echo "  stop     - Stop the bridge"
        echo "  restart  - Restart the bridge"
        echo "  status   - Check if bridge is running"
        echo "  logs     - Follow log output"
        exit 1
        ;;
esac
