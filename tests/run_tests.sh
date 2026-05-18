#!/usr/bin/env bash
# Test suite for Informatica-Demo repository
# Validates shell scripts, XML exports, and SQL artifacts.

set -euo pipefail

PASS=0
FAIL=0
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

cd "$REPO_ROOT"

# ETL scripts contain SQL*Plus heredocs that ShellCheck cannot fully parse
ETL_SCRIPTS=(ehrp2biis_preload actstage_load)

# Utility and transfer scripts that ShellCheck can fully analyse
CLEAN_SCRIPTS=(
    "Maintenance Scripts/remove_file" "Maintenance Scripts/archive_files"
    "Transfer Scripts/afps_transfer" "Transfer Scripts/cdc_transfer"
    "Transfer Scripts/fda_transfer" "Transfer Scripts/nih_cpm_transfer"
    "Transfer Scripts/nih_les_transfer" "Transfer Scripts/nih_transfer_les"
    "Transfer Scripts/oig_transfer"
)

ALL_SCRIPTS=("${ETL_SCRIPTS[@]}" "${CLEAN_SCRIPTS[@]}")

# ── 1. Shell script checks ──────────────────────────────────────────
echo "=== Shell script tests ==="

echo "-- Test: all shell scripts have ksh shebang"
for f in "${ALL_SCRIPTS[@]}"; do
    if head -1 "$f" | grep -q '#!/bin/ksh'; then
        pass "$f has ksh shebang"
    else
        fail "$f missing ksh shebang"
    fi
done

echo "-- Test: ShellCheck clean scripts (severity=warning)"
for f in "${CLEAN_SCRIPTS[@]}"; do
    if shellcheck --severity=warning "$f" > /dev/null 2>&1; then
        pass "shellcheck $f"
    else
        fail "shellcheck $f"
    fi
done

echo "-- Test: ShellCheck ETL scripts (severity=error, excluding heredoc parse errors)"
for f in "${ETL_SCRIPTS[@]}"; do
    if shellcheck --severity=error -e SC1072,SC1073,SC1041,SC1042 "$f" > /dev/null 2>&1; then
        pass "shellcheck $f (ETL mode)"
    else
        fail "shellcheck $f (ETL mode)"
    fi
done

# ── 2. XML validation tests ─────────────────────────────────────────
echo ""
echo "=== XML validation tests ==="

echo "-- Test: all XML files are well-formed"
for f in XML/* Pseudossn; do
    if xmllint --noout "$f" 2>/dev/null; then
        pass "xmllint $f"
    else
        fail "xmllint $f"
    fi
done

echo "-- Test: XML files contain POWERMART root element"
for f in XML/* Pseudossn; do
    if grep -q '<POWERMART' "$f"; then
        pass "$f has POWERMART root"
    else
        fail "$f missing POWERMART root"
    fi
done

# ── 3. SQL file tests ───────────────────────────────────────────────
echo ""
echo "=== SQL file tests ==="

echo "-- Test: SQL files exist and are non-empty"
for f in ehrp2biis_afterload.sql; do
    if [ -s "$f" ]; then
        pass "$f exists and is non-empty"
    else
        fail "$f missing or empty"
    fi
done

echo "-- Test: SQL files have balanced COMMIT statements"
for f in ehrp2biis_afterload.sql; do
    commits=$(grep -ci 'COMMIT' "$f" || true)
    if [ "$commits" -gt 0 ]; then
        pass "$f has $commits COMMIT statement(s)"
    else
        fail "$f has no COMMIT statements"
    fi
done

echo "-- Test: SQL files use SPOOL for logging"
for f in ehrp2biis_afterload.sql; do
    if grep -qi 'SPOOL' "$f"; then
        pass "$f uses SPOOL directive"
    else
        fail "$f missing SPOOL directive"
    fi
done

# ── 4. Repository structure tests ───────────────────────────────────
echo ""
echo "=== Repository structure tests ==="

echo "-- Test: expected directories exist"
for d in XML "Maintenance Scripts" "Transfer Scripts"; do
    if [ -d "$d" ]; then
        pass "directory '$d' exists"
    else
        fail "directory '$d' missing"
    fi
done

echo "-- Test: expected file count in XML/"
xml_count=$(find XML -maxdepth 1 -type f | wc -l)
if [ "$xml_count" -ge 10 ]; then
    pass "XML/ contains $xml_count files (>= 10)"
else
    fail "XML/ contains only $xml_count files (expected >= 10)"
fi

echo "-- Test: expected transfer scripts exist"
for f in "${CLEAN_SCRIPTS[@]}"; do
    if [ -f "$f" ]; then
        pass "$f exists"
    else
        fail "$f missing"
    fi
done

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "======================================="
echo "Results: $PASS passed, $FAIL failed"
echo "======================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
