#!/usr/bin/env bash
# Get the newest copy of the skill's tools, with fallbacks, so a run never stops on "GitHub not reachable".
#
#   bash <this skill's folder>/bootstrap.sh <scratch dir>
#
# First it reads only the repo's VERSION file (a few bytes). When the installed copy (this folder) already has that
# version, it is used as it is: nothing is downloaded (SOURCE=installed). Likewise a copy fetched earlier in this
# session (SOURCE=cached). Otherwise it downloads, and when the installed copy is older it prints one UPDATE line
# telling the user to reinstall the zip, so later runs also work offline with the newest version.
# Downloads try, in order, stopping at the first that works:
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

# 0. Is a download needed at all? Read only the latest VERSION.
VURLS="${JSS_VERSION_URL:-https://raw.githubusercontent.com/$REPO/main/$SUB/VERSION https://api.github.com/repos/$REPO/contents/$SUB/VERSION?ref=main}"
LATEST=""
for u in $VURLS; do
  if command -v curl >/dev/null 2>&1; then
    LATEST=$(timeout 30 curl -fsSL -H "Accept: application/vnd.github.raw" "$u" 2>>"$LOG" | tr -d '[:space:]')
  elif command -v python3 >/dev/null 2>&1; then
    LATEST=$(timeout 30 python3 -c "import sys,urllib.request as r; print(r.urlopen(r.Request(sys.argv[1], headers={'Accept': 'application/vnd.github.raw'}), timeout=25).read().decode().strip())" "$u" 2>>"$LOG")
  fi
  echo "$LATEST" | grep -Eq '^[0-9]+(\.[0-9]+)+$' && break
  note "version check failed: $u"; LATEST=""
done
INSTALLED=""
[ -f "$HERE/scripts/vet.py" ] && [ -f "$HERE/VERSION" ] && INSTALLED=$(tr -d '[:space:]' < "$HERE/VERSION")
newer() { [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }   # is $1 newer than $2
if [ -n "$LATEST" ]; then
  if [ -n "$INSTALLED" ] && ! newer "$LATEST" "$INSTALLED"; then
    echo "TOOLS=$HERE VERSION=$INSTALLED SOURCE=installed"; exit 0
  fi
  if good "$DEST" && ! newer "$LATEST" "$(tr -d '[:space:]' < "$DEST/$SUB/VERSION")"; then
    echo "TOOLS=$DEST/$SUB VERSION=$(cat "$DEST/$SUB/VERSION") SOURCE=cached"; exit 0
  fi
fi

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
  GOT=$(tr -d '[:space:]' < "$TOOLS/VERSION")
  if [ -n "$INSTALLED" ] && newer "$GOT" "$INSTALLED"; then
    echo "UPDATE: the installed skill is $INSTALLED and the latest is $GOT; this run uses $GOT. To get it without downloading each run (and when offline), download https://github.com/$REPO/raw/main/dist/us-job-search-automation.zip and upload it in Customize > Skills, replacing the old one."
  elif [ -z "$INSTALLED" ]; then
    echo "UPDATE: this installed skill has no scripts, so every run downloads them and a run stops when GitHub is unreachable. Install the full zip instead: https://github.com/$REPO/raw/main/dist/us-job-search-automation.zip (Customize > Skills, replace the old one)."
  fi
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
