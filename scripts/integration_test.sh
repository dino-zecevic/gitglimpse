#!/usr/bin/env bash
set -euo pipefail

# gitglimpse integration test suite
# Creates test repos and runs every command, capturing results.

GITGLIMPSE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR="/tmp/gitglimpse-integration-test"
RESULTS="$TEST_DIR/results.md"
PASS_COUNT=0
FAIL_COUNT=0
FAILED_TESTS=()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { echo "==> $*"; }

record_header() {
    echo "" >> "$RESULTS"
    echo "## Test $1: $2" >> "$RESULTS"
    echo "**Command:** \`$3\`" >> "$RESULTS"
    echo "**Expected:** $4" >> "$RESULTS"
}

record_output() {
    local test_num="$1"
    local output="$2"
    local pass="$3"

    if [ "$pass" = "true" ]; then
        echo "**Status:** PASS" >> "$RESULTS"
        PASS_COUNT=$((PASS_COUNT + 1))
        log "  Test $test_num: PASS"
    else
        echo "**Status:** FAIL" >> "$RESULTS"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_TESTS+=("$test_num")
        log "  Test $test_num: FAIL"
    fi
    echo "**Output:**" >> "$RESULTS"
    echo '```' >> "$RESULTS"
    echo "$output" >> "$RESULTS"
    echo '```' >> "$RESULTS"
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

log "Cleaning up previous test directory..."
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

# Reinstall gitglimpse from source to pick up template changes
log "Installing gitglimpse from source..."
pip install -e "$GITGLIMPSE_ROOT" --quiet 2>/dev/null || pip install -e "$GITGLIMPSE_ROOT"

cat > "$RESULTS" <<'HEADER'
# gitglimpse integration test results
HEADER
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')" >> "$RESULTS"

# ---------------------------------------------------------------------------
# Create test repos
# ---------------------------------------------------------------------------

log "Creating test repos..."

# --- REPO 1: test-api ---
REPO1="$TEST_DIR/test-api"
mkdir -p "$REPO1"
cd "$REPO1"
git init -q
git config user.email "tester@example.com"
git config user.name "Test User"

# feature/AUTH-42-jwt-refresh branch
git checkout -q -b feature/AUTH-42-jwt-refresh

mkdir -p tests

cat > auth.py <<'PY'
import jwt
import datetime

class JWTRefreshHandler:
    def __init__(self, secret, expiry_minutes=30):
        self.secret = secret
        self.expiry_minutes = expiry_minutes

    def generate_token(self, user_id):
        payload = {
            "user_id": user_id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=self.expiry_minutes),
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def rotate_token(self, old_token):
        payload = jwt.decode(old_token, self.secret, algorithms=["HS256"])
        return self.generate_token(payload["user_id"])
PY
git add auth.py
GIT_AUTHOR_DATE="$(date -v-2d -v9H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v9H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add JWT refresh handler with token rotation"

cat > middleware.py <<'PY'
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests = defaultdict(list)

    def is_allowed(self, client_ip):
        now = time.time()
        window_start = now - self.window
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window_start]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True
PY
git add middleware.py
GIT_AUTHOR_DATE="$(date -v-2d -v9H -v45M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v9H -v45M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add rate limiting middleware for API endpoints"

cat >> auth.py <<'PY'

    def validate_refresh_token(self, token):
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            if payload.get("exp", 0) < datetime.datetime.utcnow().timestamp():
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
PY
git add auth.py
GIT_AUTHOR_DATE="$(date -v-2d -v10H -v30M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v10H -v30M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add refresh token validation with expiry check"

cat > tests/test_auth.py <<'PY'
import pytest
from auth import JWTRefreshHandler

def test_generate_token():
    handler = JWTRefreshHandler("secret")
    token = handler.generate_token(1)
    assert token is not None

def test_rotate_token():
    handler = JWTRefreshHandler("secret")
    token = handler.generate_token(1)
    new_token = handler.rotate_token(token)
    assert new_token != token

def test_validate_refresh_token():
    handler = JWTRefreshHandler("secret")
    token = handler.generate_token(1)
    result = handler.validate_refresh_token(token)
    assert result is not None
PY
git add tests/test_auth.py
GIT_AUTHOR_DATE="$(date -v-2d -v14H -v30M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v14H -v30M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add test coverage for JWT refresh flow"

# Noise commit
echo '{"lockfileVersion": 3}' > package-lock.json
git add package-lock.json
GIT_AUTHOR_DATE="$(date -v-2d -v14H -v35M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v14H -v35M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "update lock file"

# Merge to main
git checkout -q -b main
git merge -q --no-ff feature/AUTH-42-jwt-refresh -m "Merge feature/AUTH-42-jwt-refresh into main"

# fix/BUG-87-pagination branch
git checkout -q -b fix/BUG-87-pagination

cat > orders.py <<'PY'
def get_orders(page=1, per_page=20):
    """Fetch paginated orders with correct offset calculation."""
    offset = (page - 1) * per_page  # Fixed: was page * per_page (off-by-one)
    return {"offset": offset, "limit": per_page}
PY
git add orders.py
GIT_AUTHOR_DATE="$(date -v-1d -v10H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-1d -v10H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Fix off-by-one error in orders pagination"

cat > tests/test_orders.py <<'PY'
from orders import get_orders

def test_first_page():
    result = get_orders(page=1)
    assert result["offset"] == 0

def test_second_page():
    result = get_orders(page=2)
    assert result["offset"] == 20

def test_edge_case_zero():
    # Ensure page=0 doesn't break
    result = get_orders(page=0)
    assert result["offset"] == -20
PY
git add tests/test_orders.py
GIT_AUTHOR_DATE="$(date -v-1d -v10H -v30M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-1d -v10H -v30M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add pagination edge case tests"

git checkout -q main
git merge -q --no-ff fix/BUG-87-pagination -m "Merge fix/BUG-87-pagination into main"

# --- REPO 2: test-app ---
REPO2="$TEST_DIR/test-app"
mkdir -p "$REPO2"
cd "$REPO2"
git init -q
git config user.email "tester@example.com"
git config user.name "Test User"

# Initial commit to establish main
echo "# test-app" > README.md
git add README.md
GIT_AUTHOR_DATE="$(date -v-3d '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-3d '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Initial commit"

cat > login.tsx <<'TSX'
import React, { useState } from 'react';

export const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

  const validateEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

  const handleSubmit = () => {
    if (!validateEmail(email)) {
      setError('Invalid email');
      return;
    }
    // submit login
  };

  return (
    <form onSubmit={handleSubmit}>
      <input value={email} onChange={e => setEmail(e.target.value)} />
      {error && <span>{error}</span>}
      <button type="submit">Login</button>
    </form>
  );
};
TSX
git add login.tsx
GIT_AUTHOR_DATE="$(date -v-2d -v10H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v10H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Build login form with email validation"

echo "// wip changes" >> login.tsx
git add login.tsx
GIT_AUTHOR_DATE="$(date -v-2d -v11H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v11H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "wip"

echo "// fix applied" >> login.tsx
git add login.tsx
GIT_AUTHOR_DATE="$(date -v-2d -v11H -v30M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-2d -v11H -v30M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "fix"

cat > theme.ts <<'TS'
export const darkTheme = {
  background: '#1a1a2e',
  text: '#e0e0e0',
  primary: '#0f3460',
  accent: '#e94560',
};

export const lightTheme = {
  background: '#ffffff',
  text: '#333333',
  primary: '#2196f3',
  accent: '#ff5722',
};
TS
git add theme.ts
GIT_AUTHOR_DATE="$(date -v-1d -v9H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-1d -v9H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add dark mode theme configuration"

cat > .prettierrc <<'JSON'
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2
}
JSON
git add .prettierrc
GIT_AUTHOR_DATE="$(date -v-1d -v9H -v5M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v-1d -v9H -v5M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "format code"

# Feature branch for PR testing (don't merge)
git checkout -q -b feature/TASK-55-notifications

mkdir -p tests

cat > notifications.py <<'PY'
import smtplib
from email.mime.text import MIMEText

class EmailNotificationService:
    def __init__(self, smtp_host, smtp_port=587):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def send(self, to, subject, body):
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["To"] = to
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.send_message(msg)
        return True
PY
git add notifications.py
GIT_AUTHOR_DATE="$(date -v9H '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v9H '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Implement email notification service"

cat > tests/test_notifications.py <<'PY'
from unittest.mock import patch, MagicMock
from notifications import EmailNotificationService

def test_send_email():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        svc = EmailNotificationService("smtp.test.com")
        result = svc.send("user@test.com", "Test", "Hello")
        assert result is True
PY
git add tests/test_notifications.py
GIT_AUTHOR_DATE="$(date -v9H -v30M '+%Y-%m-%dT%H:%M:%S')" GIT_COMMITTER_DATE="$(date -v9H -v30M '+%Y-%m-%dT%H:%M:%S')" \
  git commit -q -m "Add notification tests"

# --- REPO 3: test-empty ---
REPO3="$TEST_DIR/test-empty"
mkdir -p "$REPO3"
cd "$REPO3"
git init -q

log "Test repos created."

# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

cd "$TEST_DIR"

# ---- Test 1: glimpse --help ----
log "Running Test 1..."
record_header 1 "glimpse --help" "glimpse --help" "Shows all commands: standup, week, pr, config, init"
OUTPUT=$(glimpse --help 2>&1) || true
PASS="true"
for cmd in standup week pr config init; do
    if ! echo "$OUTPUT" | grep -q "$cmd"; then
        PASS="false"
        break
    fi
done
record_output 1 "$OUTPUT" "$PASS"

# ---- Test 2: glimpse standup (single project, good commits) ----
log "Running Test 2..."
record_header 2 "glimpse standup (single project, good commits)" \
    "cd test-api && glimpse standup --since \"3 days ago\" --author \"tester@example.com\"" \
    "Shows grouped tasks by day, ticket IDs (AUTH-42, BUG-87), noise filtered, estimated effort label"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --skip-setup 2>&1) || true
PASS="true"
# Should have some output and not be a crash
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
if [ -z "$OUTPUT" ]; then
    PASS="false"
fi
record_output 2 "$OUTPUT" "$PASS"

# ---- Test 3: glimpse standup --json (single project) ----
log "Running Test 3..."
record_header 3 "glimpse standup --json (single project)" \
    "cd test-api && glimpse standup --since \"3 days ago\" --author \"tester@example.com\" --json" \
    "Valid JSON with days array, ticket fields, effort_note, filtered_commits"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --json --skip-setup 2>&1) || true
PASS="true"
echo "$OUTPUT" | python3 -m json.tool > /dev/null 2>&1 || PASS="false"
if [ "$PASS" = "true" ]; then
    echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'days' in d" 2>/dev/null || PASS="false"
fi
echo "**Validation:** piped through python3 -m json.tool" >> "$RESULTS"
record_output 3 "$OUTPUT" "$PASS"

# ---- Test 4: glimpse standup --no-filter-noise ----
log "Running Test 4..."
record_header 4 "glimpse standup --no-filter-noise" \
    "cd test-api && glimpse standup --since \"3 days ago\" --author \"tester@example.com\" --no-filter-noise" \
    "Shows noise commits that were filtered in test 2 (lock file update)"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --no-filter-noise --skip-setup 2>&1) || true
PASS="true"
# With no-filter-noise, lock file commit should appear somewhere
# We just check it doesn't crash and produces output
if [ -z "$OUTPUT" ]; then
    PASS="false"
fi
record_output 4 "$OUTPUT" "$PASS"

# ---- Test 5: glimpse standup (vague commits) ----
log "Running Test 5..."
record_header 5 "glimpse standup (vague commits)" \
    "cd test-app && glimpse standup --since \"3 days ago\" --author \"tester@example.com\"" \
    "Handles vague messages (wip, fix) — should show file-path-based summary. format code filtered as noise."
cd "$TEST_DIR/test-app"
git checkout -q main 2>/dev/null || true
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
record_output 5 "$OUTPUT" "$PASS"

# ---- Test 6: glimpse standup (multi-project) ----
log "Running Test 6..."
record_header 6 "glimpse standup (multi-project)" \
    "cd /tmp/gitglimpse-integration-test && glimpse standup --since \"3 days ago\" --author \"tester@example.com\"" \
    "Found 2 projects (test-api, test-app). Grouped by project. test-empty should not appear (no commits). Noise filtered."
cd "$TEST_DIR"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
# Should mention projects found
if ! echo "$OUTPUT" | grep -qi "project\|test-api\|test-app\|Found"; then
    PASS="false"
fi
record_output 6 "$OUTPUT" "$PASS"

# ---- Test 7: glimpse standup --json (multi-project) ----
log "Running Test 7..."
record_header 7 "glimpse standup --json (multi-project)" \
    "cd /tmp/gitglimpse-integration-test && glimpse standup --since \"3 days ago\" --author \"tester@example.com\" --json" \
    "Valid JSON with multi_project: true, projects array"
cd "$TEST_DIR"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --json --skip-setup 2>/dev/null) || true
PASS="true"
echo "$OUTPUT" | python3 -m json.tool > /dev/null 2>&1 || PASS="false"
echo "**Validation:** piped through python3 -m json.tool" >> "$RESULTS"
record_output 7 "$OUTPUT" "$PASS"

# ---- Test 8: glimpse standup --format markdown ----
log "Running Test 8..."
record_header 8 "glimpse standup --format markdown" \
    "cd test-api && glimpse standup --format markdown --since \"3 days ago\" --author \"tester@example.com\"" \
    "Markdown report with file details, insertions/deletions, ticket IDs in headers"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse standup --format markdown --since "3 days ago" --author "tester@example.com" --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
if [ -z "$OUTPUT" ]; then
    PASS="false"
fi
# Verify it's markdown format (has # heading)
if ! echo "$OUTPUT" | grep -q "^# Daily Report"; then
    PASS="false"
fi
record_output 8 "$OUTPUT" "$PASS"

# ---- Test 9: glimpse week ----
log "Running Test 9..."
record_header 9 "glimpse week" \
    "cd test-api && glimpse week --author \"tester@example.com\"" \
    "Weekly summary with per-day breakdown, day totals, week total"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse week --author "tester@example.com" --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
if [ -z "$OUTPUT" ]; then
    PASS="false"
fi
record_output 9 "$OUTPUT" "$PASS"

# ---- Test 10: glimpse week --json ----
log "Running Test 10..."
record_header 10 "glimpse week --json" \
    "cd test-api && glimpse week --author \"tester@example.com\" --json" \
    "Valid JSON with days array, day_name fields, week totals"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse week --author "tester@example.com" --json --skip-setup 2>&1) || true
PASS="true"
echo "$OUTPUT" | python3 -m json.tool > /dev/null 2>&1 || PASS="false"
echo "**Validation:** piped through python3 -m json.tool" >> "$RESULTS"
record_output 10 "$OUTPUT" "$PASS"

# ---- Test 11: glimpse pr (with commits on branch) ----
log "Running Test 11..."
record_header 11 "glimpse pr (with commits on branch)" \
    "cd test-app && git checkout feature/TASK-55-notifications && glimpse pr" \
    "PR summary showing branch vs main, ticket TASK-55 detected, changes listed, stats shown"
cd "$TEST_DIR/test-app"
git checkout -q feature/TASK-55-notifications
OUTPUT=$(glimpse pr --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
if [ -z "$OUTPUT" ]; then
    PASS="false"
fi
record_output 11 "$OUTPUT" "$PASS"

# ---- Test 12: glimpse pr --json ----
log "Running Test 12..."
record_header 12 "glimpse pr --json" \
    "cd test-app && glimpse pr --json" \
    "Valid JSON with branch, base, ticket, tasks, diff_snippet, files_changed"
cd "$TEST_DIR/test-app"
OUTPUT=$(glimpse pr --json --skip-setup 2>&1) || true
PASS="true"
echo "$OUTPUT" | python3 -m json.tool > /dev/null 2>&1 || PASS="false"
echo "**Validation:** piped through python3 -m json.tool" >> "$RESULTS"
record_output 12 "$OUTPUT" "$PASS"

# ---- Test 13: glimpse pr (empty branch) ----
log "Running Test 13..."
record_header 13 "glimpse pr (empty branch)" \
    "cd test-api && git checkout -b empty-test && glimpse pr" \
    "Message about no commits on this branch. Should NOT crash."
cd "$TEST_DIR/test-api"
git checkout -q -b empty-test
OUTPUT=$(glimpse pr --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
record_output 13 "$OUTPUT" "$PASS"
git checkout -q main
git branch -q -D empty-test

# ---- Test 14: glimpse pr (from empty repo) ----
log "Running Test 14..."
record_header 14 "glimpse pr (from empty repo)" \
    "cd test-empty && glimpse pr 2>&1" \
    "Error message about empty repo or no commits. Should NOT crash."
cd "$TEST_DIR/test-empty"
OUTPUT=$(glimpse pr --skip-setup 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
record_output 14 "$OUTPUT" "$PASS"

# ---- Test 15: glimpse config show ----
log "Running Test 15..."
record_header 15 "glimpse config show" \
    "glimpse config show" \
    "Table with all config settings, no old fields like prefer_diff"
OUTPUT=$(glimpse config show 2>&1) || true
PASS="true"
if echo "$OUTPUT" | grep -qi "traceback"; then
    PASS="false"
fi
if echo "$OUTPUT" | grep -qi "prefer_diff"; then
    PASS="false"
fi
record_output 15 "$OUTPUT" "$PASS"

# ---- Test 16: glimpse init --force ----
log "Running Test 16..."
record_header 16 "glimpse init --force" \
    "cd test-api && glimpse init --force" \
    "Creates 4 files: standup.md, report.md, week.md, pr.md. No Context mode print line."
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse init --force 2>&1) || true
PASS="true"
# Check 4 files created
for f in standup.md report.md week.md pr.md; do
    if [ ! -f "$TEST_DIR/test-api/.claude/commands/$f" ]; then
        PASS="false"
        break
    fi
done
# No "Context mode" line
if echo "$OUTPUT" | grep -qi "Context mode"; then
    PASS="false"
fi
record_output 16 "$OUTPUT" "$PASS"

# ---- Test 17: glimpse init command files use --context both ----
log "Running Test 17..."
record_header 17 "glimpse init command files use --context both" \
    "cat test-api/.claude/commands/standup.md | grep context" \
    "Contains --context both NOT --context commits"
cd "$TEST_DIR"
OUTPUT=$(cat test-api/.claude/commands/standup.md | grep "context" 2>&1) || true
PASS="true"
if ! echo "$OUTPUT" | grep -q "\-\-context both"; then
    PASS="false"
fi
record_output 17 "$OUTPUT" "$PASS"

# ---- Test 18: glimpse init pr.md uses --context both ----
log "Running Test 18..."
record_header 18 "glimpse init pr.md uses --context both" \
    "cat test-api/.claude/commands/pr.md | grep context" \
    "Contains --context both"
OUTPUT=$(cat test-api/.claude/commands/pr.md | grep "context" 2>&1) || true
PASS="true"
if ! echo "$OUTPUT" | grep -q "\-\-context both"; then
    PASS="false"
fi
record_output 18 "$OUTPUT" "$PASS"

# ---- Test 19: noise filtering verification ----
log "Running Test 19..."
record_header 19 "noise filtering verification" \
    "glimpse standup --json (with and without --no-filter-noise)" \
    "Noise commit filtered by default (0 matches), shown with --no-filter-noise (1 match)"
cd "$TEST_DIR/test-api"
FILTERED_OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --json --skip-setup 2>/dev/null) || true
FILTERED_COUNT=$(echo "$FILTERED_OUTPUT" | python3 -m json.tool 2>/dev/null | grep -c "update lock file" || true)
UNFILTERED_OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --no-filter-noise --json --skip-setup 2>/dev/null) || true
UNFILTERED_COUNT=$(echo "$UNFILTERED_OUTPUT" | python3 -m json.tool 2>/dev/null | grep -c "update lock file" || true)
PASS="true"
if [ "$FILTERED_COUNT" != "0" ]; then
    PASS="false"
fi
if [ "$UNFILTERED_COUNT" != "1" ]; then
    # Might appear more than once in nested fields — just check it's > 0
    if [ "$UNFILTERED_COUNT" = "0" ]; then
        PASS="false"
    fi
fi
COMBINED="Filtered (expected 0): $FILTERED_COUNT
Unfiltered (expected >=1): $UNFILTERED_COUNT

--- Filtered JSON ---
$FILTERED_OUTPUT

--- Unfiltered JSON ---
$UNFILTERED_OUTPUT"
record_output 19 "$COMBINED" "$PASS"

# ---- Test 20: ticket extraction verification ----
log "Running Test 20..."
record_header 20 "ticket extraction verification" \
    "glimpse standup --json | grep ticket" \
    "Shows AUTH-42 and BUG-87 ticket values"
cd "$TEST_DIR/test-api"
OUTPUT=$(glimpse standup --since "3 days ago" --author "tester@example.com" --json --skip-setup 2>&1) || true
TICKET_LINES=$(echo "$OUTPUT" | python3 -m json.tool 2>/dev/null | grep "ticket" || echo "")
PASS="true"
if ! echo "$TICKET_LINES" | grep -q "AUTH-42"; then
    PASS="false"
fi
if ! echo "$TICKET_LINES" | grep -q "BUG-87"; then
    PASS="false"
fi
record_output 20 "$TICKET_LINES" "$PASS"

# ---- Test 21: pytest ----
log "Running Test 21..."
record_header 21 "pytest" \
    "cd $GITGLIMPSE_ROOT && pytest -v" \
    "All tests pass"
cd "$GITGLIMPSE_ROOT"
OUTPUT=$(python3 -m pytest -v 2>&1) || true
PASS="true"
if ! echo "$OUTPUT" | grep -q "passed"; then
    PASS="false"
fi
if echo "$OUTPUT" | grep -q "FAILED\|ERROR"; then
    PASS="false"
fi
# Extract summary line
SUMMARY_LINE=$(echo "$OUTPUT" | tail -5)
record_output 21 "$SUMMARY_LINE" "$PASS"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo "" >> "$RESULTS"
echo "## Summary" >> "$RESULTS"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "- Total tests: $TOTAL" >> "$RESULTS"
echo "- Passed: $PASS_COUNT" >> "$RESULTS"
echo "- Failed: $FAIL_COUNT" >> "$RESULTS"
if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo "- Failed tests: ${FAILED_TESTS[*]}" >> "$RESULTS"
else
    echo "- Failed tests: none" >> "$RESULTS"
fi

log ""
log "============================================"
log "  Results: $PASS_COUNT/$TOTAL passed"
if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    log "  Failed: ${FAILED_TESTS[*]}"
fi
log "  Report: $RESULTS"
log "============================================"
