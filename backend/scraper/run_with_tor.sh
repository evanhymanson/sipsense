#!/usr/bin/env bash
#
# Run the Whiskybase scraper with Tor for IP rotation.
#
# This script:
#   1. Starts the Tor SOCKS proxy (standalone tor daemon, NOT Tor Browser)
#   2. Waits for Tor to connect and be ready on port 9050
#   3. Runs the Whiskybase scraper through Tor
#   4. Cleans up Tor on exit
#
# Setup (one-time):
#   brew install tor
#
# Usage:
#   cd backend
#   bash scraper/run_with_tor.sh                  # resume from last position
#   bash scraper/run_with_tor.sh --no-resume      # start from beginning
#   bash scraper/run_with_tor.sh --limit 1000     # limit whiskeys

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
TOR_SOCKS_PORT=9050
TOR_CONTROL_PORT=9051
TOR_PROXY="socks5://127.0.0.1:${TOR_SOCKS_PORT}"
TOR_PID_FILE="/tmp/sipsense_tor.pid"
MAX_WAIT=60  # seconds to wait for Tor to connect

# Parse our wrapper flags (pass the rest through to run.py)
RESUME="--resume"
EXTRA_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --no-resume) RESUME="" ;;
        *) EXTRA_ARGS+=("$arg") ;;
    esac
done

# ─── Helpers ─────────────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo ">>> Cleaning up..."
    if [[ -f "$TOR_PID_FILE" ]]; then
        TOR_PID=$(cat "$TOR_PID_FILE")
        if kill -0 "$TOR_PID" 2>/dev/null; then
            echo ">>> Stopping Tor (PID $TOR_PID)..."
            kill "$TOR_PID" 2>/dev/null || true
            wait "$TOR_PID" 2>/dev/null || true
        fi
        rm -f "$TOR_PID_FILE"
    fi
    echo ">>> Done."
}

trap cleanup EXIT INT TERM

check_port() {
    nc -z 127.0.0.1 "$1" 2>/dev/null
}

# ─── Check tor is installed ──────────────────────────────────────────────────

if ! command -v tor &>/dev/null; then
    echo "ERROR: 'tor' is not installed."
    echo ""
    echo "Install it with:"
    echo "  brew install tor"
    echo ""
    echo "This installs the standalone Tor daemon (lightweight, ~15MB)."
    echo "It's separate from Tor Browser and works better for scripting."
    exit 1
fi

# ─── Start Tor ───────────────────────────────────────────────────────────────

# Check if Tor is already running on our ports
if check_port "$TOR_SOCKS_PORT"; then
    echo ">>> Tor already running on port $TOR_SOCKS_PORT — using existing instance."
else
    echo ">>> Starting Tor daemon..."

    # Create a minimal torrc for our use case
    TOR_DATA_DIR="/tmp/sipsense_tor_data"
    mkdir -p "$TOR_DATA_DIR"

    TORRC="/tmp/sipsense_torrc"
    cat > "$TORRC" <<EOF
SocksPort $TOR_SOCKS_PORT
ControlPort $TOR_CONTROL_PORT
DataDirectory $TOR_DATA_DIR
# Allow unauthenticated control connections (local only)
CookieAuthentication 0
HashedControlPassword
# Rotate circuits more aggressively
MaxCircuitDirtiness 300
NewCircuitPeriod 30
# Log to stdout
Log notice stdout
EOF

    # Launch tor in background
    tor -f "$TORRC" &
    TOR_PID=$!
    echo "$TOR_PID" > "$TOR_PID_FILE"

    # Wait for Tor to bootstrap
    echo ">>> Waiting for Tor to connect (up to ${MAX_WAIT}s)..."
    WAITED=0
    while ! check_port "$TOR_SOCKS_PORT"; do
        sleep 1
        WAITED=$((WAITED + 1))
        if [[ $WAITED -ge $MAX_WAIT ]]; then
            echo "ERROR: Tor did not start within ${MAX_WAIT}s."
            echo "Check if another process is using port $TOR_SOCKS_PORT."
            exit 1
        fi
        # Show progress every 5 seconds
        if [[ $((WAITED % 5)) -eq 0 ]]; then
            echo ">>>   ...still waiting ($WAITED/${MAX_WAIT}s)"
        fi
    done

    echo ">>> Tor is ready! SOCKS proxy at $TOR_PROXY"

    # Give Tor a moment to fully bootstrap circuits
    sleep 3

    # Verify we can reach the internet through Tor
    echo ">>> Verifying Tor connection..."
    TOR_IP=$(curl --max-time 15 --socks5-hostname "127.0.0.1:$TOR_SOCKS_PORT" -s https://api.ipify.org 2>/dev/null || echo "FAILED")
    if [[ "$TOR_IP" == "FAILED" ]]; then
        echo "WARNING: Could not verify Tor connection. Proceeding anyway..."
    else
        echo ">>> Tor exit IP: $TOR_IP"
    fi
fi

# ─── Run the scraper ─────────────────────────────────────────────────────────

echo ""
echo ">>> Starting Whiskybase scraper through Tor..."
echo ">>> Command: python3 -m scraper.run --source whiskybase $RESUME --proxy $TOR_PROXY ${EXTRA_ARGS[*]:-}"
echo ""

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    python3 -m scraper.run \
        --source whiskybase \
        $RESUME \
        --proxy "$TOR_PROXY" \
        "${EXTRA_ARGS[@]}"
else
    python3 -m scraper.run \
        --source whiskybase \
        $RESUME \
        --proxy "$TOR_PROXY"
fi

echo ""
echo ">>> Scraper finished."
