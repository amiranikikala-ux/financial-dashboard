#!/usr/bin/env bash
# Stop hook — detect language regression in latest assistant turn.
# Patterns:
#   1. Georgian filler "ცადო"/"ცადობს" appearing 3+ times
#   2. Partial Latin tokens (Georgian-Latin glue): magram, magari, magrad
#
# On detection: writes flag file, increments counter, emits systemMessage.

set -u

INPUT="$(cat)"
PROJECT_ROOT="$(pwd)"
FLAG_FILE="$PROJECT_ROOT/.claude/regression_detected.flag"
COUNT_FILE="$PROJECT_ROOT/.claude/regression_count.txt"

# Run detection in Python (jq unavailable on Windows Git Bash; Python 3.14 is on PATH)
RESULT="$(python - <<'PYEOF' "$INPUT"
import json, sys, re, os

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception:
    sys.exit(0)

transcript_path = payload.get("transcript_path") or ""
if not transcript_path or not os.path.exists(transcript_path):
    sys.exit(0)

# Collect text from latest assistant turn (walk back until user entry).
texts = []
try:
    with open(transcript_path, encoding="utf-8") as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)

for line in reversed(lines):
    try:
        d = json.loads(line)
    except Exception:
        continue
    t = d.get("type")
    if t == "user":
        break
    if t != "assistant":
        continue
    msg = d.get("message", {})
    content = msg.get("content", []) if isinstance(msg, dict) else []
    if not isinstance(content, list):
        continue
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            txt = block.get("text") or ""
            if txt:
                texts.append(txt)

if not texts:
    sys.exit(0)

full_text = "\n".join(reversed(texts))

# Pattern 1: ცადო / ცადობს repeated 3+ times
tsado_count = len(re.findall(r"ცადო(?:ბს)?", full_text))

# Pattern 2: partial Latin tokens with word boundaries (case-insensitive)
latin_pattern = re.compile(r"\b(magram|magari|magrad)\b", re.IGNORECASE)
latin_match = latin_pattern.search(full_text)

reasons = []
if tsado_count >= 3:
    reasons.append(f"ცადო/ცადობს repeated {tsado_count}x")
if latin_match:
    reasons.append(f"Latin glue token: {latin_match.group(0)!r}")

if not reasons:
    sys.exit(0)

# Output reason joined with " + " for shell to consume
print(" + ".join(reasons))
PYEOF
)"

# Empty result = no regression
[ -z "$RESULT" ] && exit 0

# --- Regression detected ---
TIMESTAMP="$(date +%Y-%m-%dT%H:%M:%S%z)"
SESSION_ID="$(printf '%s' "$INPUT" | python -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('session_id', 'unknown'))" 2>/dev/null || echo unknown)"

# Increment persistent counter
COUNT="$(cat "$COUNT_FILE" 2>/dev/null || echo 0)"
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNT_FILE"

# Write flag file
cat > "$FLAG_FILE" <<EOF
timestamp: $TIMESTAMP
count: $COUNT
reason: $RESULT
session: $SESSION_ID
EOF

# Stderr message (visible in terminal)
echo "🚨 RESTART REQUIRED — language regression pattern detected: $RESULT" >&2

# JSON systemMessage for Claude Code UI
printf '{"systemMessage": "🚨 Language regression detected (#%s): %s. Recommend new chat — flag at .claude/regression_detected.flag, count at .claude/regression_count.txt."}\n' "$COUNT" "$RESULT"

exit 0
