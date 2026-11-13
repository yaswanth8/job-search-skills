#!/usr/bin/env python3
"""Self-test, version check and zip build for the job-search skills.

Usage: python3 tools/build.py [--check]   (--check: test only, don't rebuild dist/)

1. Runs the automation skill's back-test against the sample profile.
2. Checks that the blank profile template loads.
3. Checks that skills/us-job-search-automation/VERSION matches the "Version:" line in its SKILL.md
   and has a CHANGELOG entry.
4. Rebuilds dist/<skill>.zip for each skill (top-level folder = skill name, no caches).
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO = ROOT / "skills" / "us-job-search-automation"
PROFILE = ROOT / "skills" / "job-search-profile"


def fail(msg):
    sys.exit(f"build: {msg}")


def main():
    check_only = "--check" in sys.argv
    r = subprocess.run([sys.executable, "-B", str(AUTO / "scripts" / "run_evals.py")], capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)
    if r.returncode:
        print(r.stdout)
        fail("self-test failed")

    sys.path.insert(0, str(AUTO / "scripts"))
    from jobkit_core import load_profile  # noqa: E402
    load_profile(PROFILE / "SKILL.md")
    print("profile template loads")

    version = (AUTO / "VERSION").read_text().strip()
    m = re.search(r"^Version:\s*([0-9.]+)", (AUTO / "SKILL.md").read_text(), re.M)
    if not m or m.group(1) != version:
        fail(f"VERSION {version} does not match the SKILL.md Version line ({m.group(1) if m else 'missing'})")
    if f"## {version}" not in (ROOT / "CHANGELOG.md").read_text():
        fail(f"CHANGELOG.md has no '## {version}' entry")
    print(f"version {version} consistent")
    boot = AUTO / "bootstrap.sh"
    if not boot.exists() or subprocess.run(["bash", "-n", str(boot)]).returncode:
        fail("bootstrap.sh is missing or does not parse: installs would stop when GitHub is unreachable")
    print("bootstrap.sh parses")

    if check_only:
        return
    (ROOT / "dist").mkdir(exist_ok=True)
    for skill in (AUTO, PROFILE):
        out = ROOT / "dist" / f"{skill.name}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(skill.rglob("*")):
                rel = f.relative_to(skill)
                # The installed copy is what bootstrap.sh falls back to when GitHub is unreachable, so it carries every
                # script, snippet and reference; the back-test (evals/, run_evals.py) stays in the repo.
                if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and rel.parts[0] != "evals" and f.name != "run_evals.py":
                    info = zipfile.ZipInfo.from_file(f, f"{skill.name}/{rel}")
                    if f.suffix == ".sh":
                        info.external_attr = 0o100755 << 16
                    z.writestr(info, f.read_bytes(), zipfile.ZIP_DEFLATED)
        print(f"built {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
