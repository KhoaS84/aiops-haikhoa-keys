#!/usr/bin/env bash
# inject.sh — Simulate the AWS S3 2017-02-28 operator typo
#
# WHAT THIS SIMULATES:
# The operator intended to run: docker compose stop billing-1
# But due to a typo / over-broad input, the command targets ALL containers.
#
# This is the core of the incident: no guardrail prevented the blast radius
# from expanding beyond the intended subsystem.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR"

echo "============================================================"
echo " AWS S3 2017-02-28 OUTAGE REPRODUCTION"
echo " Failure mode: Operator action without guardrail"
echo "============================================================"
echo ""

# --- Pre-injection: verify all services are healthy ---
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] PRE-CHECK: Verifying all 5 services are running..."
docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}"
echo ""

RUNNING_COUNT=$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps --status running -q | wc -l)
if [ "$RUNNING_COUNT" -lt 5 ]; then
    echo "ERROR: Expected 5 running services, found $RUNNING_COUNT. Run start_reproduction.sh first."
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] All 5 services confirmed running."
echo ""

# --- The typo ---
echo "============================================================"
echo " INJECTING FAILURE: Operator typo"
echo ""
echo " INTENDED command:  docker compose stop billing-1"
echo " ACTUAL command:    docker compose stop  (no service specified!)"
echo "============================================================"
echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Operator executes over-broad stop command..."

# Simulate: stop ALL services (the typo)
docker compose -f "$COMPOSE_DIR/docker-compose.yml" stop

echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Command completed."
echo ""

# --- Post-injection: show the damage ---
echo "============================================================"
echo " IMPACT ASSESSMENT"
echo "============================================================"
echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Service status after typo:"
docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}"
echo ""

RUNNING_AFTER=$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps --status running -q | wc -l)
STOPPED=$(( 5 - RUNNING_AFTER ))

echo "--- DAMAGE SUMMARY ---"
echo "Services stopped: $STOPPED / 5"
echo ""
echo "Subsystems affected:"
echo "  [INTENDED]     billing   — 1 container stopped (this was correct)"
echo "  [UNINTENDED]   index     — 2 containers stopped → cannot resolve object metadata"
echo "  [UNINTENDED]   placement — 2 containers stopped → cannot route new object writes"
echo ""
echo "Real-world equivalent:"
echo "  - S3 GET/PUT/LIST all fail because index subsystem is down"
echo "  - No new objects can be placed because placement subsystem is down"
echo "  - Half the internet depends on S3 → cascading failures across AWS customers"
echo ""
echo "Missing guardrails that allowed this:"
echo "  1. No blast-radius limit on the removal tool"
echo "  2. No confirmation prompt for commands affecting >N servers"
echo "  3. No rate-limit on concurrent server removal"
echo "  4. No pre-check: 'this will remove servers from 3 subsystems, continue?'"
echo ""
echo "============================================================"
echo " Reproduction complete. Capture timeline data now."
echo "============================================================"
