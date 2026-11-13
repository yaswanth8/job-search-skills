#!/usr/bin/env bash
# Get the newest copy of the skill's tools, with fallbacks, so a run never stops on "GitHub not reachable".
#
#   bash <this skill's folder>/bootstrap.sh <scratch dir>
#
# Tries, in order, stopping at the first that works:
#   1. git clone --depth 1            (github.com)
#   2. the same files as a tarball    (codeload.github.com, then api.github.com, then github.com/archive)
#   3. Python's urllib for step 2     (when curl is missing)
#   4. a copy fetched earlier in this session (<scratch>/jss)
#   5. the copy bundled with the installed skill (this folder), if it has scripts/
# A failed or interrupted download never replaces a good copy: each try unpacks into a fresh temp folder.
# Last line, always:  TOOLS=<dir> VERSION=<v> SOURCE=<git|tarball|python|cached|bundled>
# Exit 1 only when no copy with scripts exists anywhere (then the run cannot go on).
set -u
SCRATCH="${1:-/tmp}"
REPO="yaswanth8/job-search-skills"
SUB="skills/us-job-search-automation"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRATCH/jss"
TMP="$SCRATCH/jss.tmp.$$"
LOG="$SCRATCH/jss.log"
mkdir -p "$SCRATCH"; : > "$LOG"
SRC=""

good() { [ -f "$1/$SUB/VERSION" ] && [ -f "$1/$SUB/scripts/vet.py" ] && [ -f "$1/$SUB/SKILL.md" ]; }
note() { echo "$*" >> "$LOG"; }

# 1. git (one retry: the session's git proxy answers 429 when two transfers overlap)
if command -v git >/dev/null 2>&1; then
  for attempt in 1 2; do
    rm -rf "$TMP"
    if timeout 180 git clone --depth 1 -q "https://github.com/$REPO" "$TMP" >>"$LOG" 2>&1 && good "$TMP"; then SRC=git; break; fi
    note "git clone attempt $attempt failed"; sleep 5
  done
fi

# 2. tarball with curl
URLS="https://codeload.github.com/$REPO/tar.gz/refs/heads/main https://api.github.com/repos/$REPO/tarball/main https://github.com/$REPO/archive/refs/heads/main.tar.gz"
if [ -z "$SRC" ] && command -v curl >/dev/null 2>&1; then
  for u in $URLS; do
    rm -rf "$TMP"; mkdir -p "$TMP"
    if timeout 120 curl -fsSL --retry 2 "$u" 2>>"$LOG" | tar xz -C "$TMP" --strip-components=1 2>>"$LOG" && good "$TMP"; then SRC=tarball; break; fi
    note "tarball failed: $u"
  done
fi

# 3. tarball with Python (no curl)
if [ -z "$SRC" ] && command -v python3 >/dev/null 2>&1; then
  for u in $URLS; do
    rm -rf "$TMP"; mkdir -p "$TMP"
    if timeout 120 python3 - "$u" "$TMP" >>"$LOG" 2>&1 <<'PY'
import io, sys, tarfile, urllib.request
url, dest = sys.argv[1], sys.argv[2]
data = urllib.request.urlopen(url, timeout=90).read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    for m in t.getmembers():
        parts = m.name.split("/", 1)
        if len(parts) < 2 or not parts[1] or m.issym() or m.islnk() or ".." in parts[1].split("/"):
            continue
        m.name = parts[1]
        t.extract(m, dest)
PY
    then good "$TMP" && { SRC=python; break; }; fi
    note "python download failed: $u"
  done
fi

if [ -n "$SRC" ]; then
  rm -rf "$DEST"; mv "$TMP" "$DEST"; TOOLS="$DEST/$SUB"
else
  rm -rf "$TMP"
  if good "$DEST"; then TOOLS="$DEST/$SUB"; SRC=cached
  elif [ -f "$HERE/scripts/vet.py" ] && [ -f "$HERE/VERSION" ]; then TOOLS="$HERE"; SRC=bundled
  else
    echo "GitHub could not be reached and this installed copy has no scripts/. Details: $LOG"
    echo "Fix: allow github.com and codeload.github.com in Claude's code-execution network settings, or install the full skill zip from https://github.com/$REPO/tree/main/dist"
    exit 1
  fi
  echo "NOTE: GitHub could not be reached (details in $LOG); using the $SRC copy. Allow github.com and codeload.github.com in Claude's code-execution network settings to get updates."
fi
echo "TOOLS=$TOOLS VERSION=$(cat "$TOOLS/VERSION") SOURCE=$SRC"
