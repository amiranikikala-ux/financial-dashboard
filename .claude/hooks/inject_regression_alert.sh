#!/usr/bin/env bash
# UserPromptSubmit hook — surface unread language regression alerts to Claude.
#
# When the Stop hook detects regression in Claude's previous response, it writes
# .claude/regression_detected.flag. This hook reads the fresh flag (< 10 min old)
# and feeds it into Claude's next-turn context via additionalContext. After
# emitting, the flag is consumed (deleted) so it doesn't replay forever.

set -u

PROJECT_ROOT="$(pwd)"
FLAG_FILE="$PROJECT_ROOT/.claude/regression_detected.flag"

[ ! -f "$FLAG_FILE" ] && exit 0

RESULT="$(python - <<'PYEOF' "$FLAG_FILE"
import sys, os, time, json

flag_path = sys.argv[1]
if not os.path.exists(flag_path):
    sys.exit(0)

mtime = os.path.getmtime(flag_path)
age = time.time() - mtime
if age > 600:
    sys.exit(0)

with open(flag_path, encoding="utf-8") as f:
    content = f.read().strip()

msg = (
    "🚨 LANGUAGE REGRESSION DETECTED in your previous response (auto-flagged by Stop hook):\n"
    f"{content}\n\n"
    "WRONG forms (NOT real Georgian morphology):\n"
    "  ცადობს / ცადობდი / ცადობდა / ცადობდით — these are NOT real Georgian verbs.\n\n"
    "CORRECT forms (verb stem is ცდილ-, not ცადო-):\n"
    "  ცდილობს / ცდილობდი / ცდილობდა / ცდილობდით\n"
    "  Alternative nouns: ცდა (attempt) / მცდელობა (attempt) / ცდელი (one who tries)\n\n"
    "Self-correct in this turn. Avoid the substring „ცადო\" entirely except when quoting the user."
)

out = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": msg
    }
}
print(json.dumps(out, ensure_ascii=False))

# Consume the flag — move to history so it doesn't replay
import shutil
hist_dir = os.path.join(os.path.dirname(flag_path), "regression_history")
os.makedirs(hist_dir, exist_ok=True)
ts = time.strftime("%Y-%m-%dT%H-%M-%S")
shutil.move(flag_path, os.path.join(hist_dir, f"{ts}_consumed.flag"))
PYEOF
)"

[ -z "$RESULT" ] && exit 0

echo "$RESULT"
exit 0
