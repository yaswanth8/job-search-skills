#!/usr/bin/env python3
"""Self-test, version check and zip build for the job-search skills.

Usage: python3 tools/build.py [--check]   (--check: test only, don't rebuild dist/)

1. Runs the automation skill's back-test against the sample profile.
2. Checks that the blank profile template loads.
3. Checks that skills/us-job-search-automation/VERSION matches the "Version:" line in its SKILL.md
   and has a CHANGELOG entry.
4. Rebuilds dist/<skill>.zip for each skill (top-level folder = skill name, no caches).
5. Checks that each dist zip matches skills/ file for file (with --check too, so CI fails on a stale zip).
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

    if not check_only:
        (ROOT / "dist").mkdir(exist_ok=True)
        for skill in (AUTO, PROFILE):
            out = ROOT / "dist" / f"{skill.name}.zip"
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                for name, f in packaged(skill).items():
                    info = zipfile.ZipInfo.from_file(f, name)
                    if f.suffix == ".sh":
                        info.external_attr = 0o100755 << 16
                    z.writestr(info, f.read_bytes(), zipfile.ZIP_DEFLATED)
            print(f"built {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")

    # The zip is what people install, and bootstrap.sh compares its VERSION file with GitHub's on every run. A zip
    # built before a version bump (or never rebuilt) makes every install look outdated, so it must match skills/.
    for skill in (AUTO, PROFILE):
        out = ROOT / "dist" / f"{skill.name}.zip"
        if not out.exists():
            fail(f"{out.relative_to(ROOT)} is missing: run python3 tools/build.py")
        want = {name: f.read_bytes() for name, f in packaged(skill).items()}
        with zipfile.ZipFile(out) as z:
            have = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
        stale = sorted(n for n in want.keys() | have.keys() if want.get(n) != have.get(n))
        if stale:
            fail(f"{out.relative_to(ROOT)} is out of date ({', '.join(stale[:5])}{' ...' if len(stale) > 5 else ''}): run python3 tools/build.py and commit dist/")
        if skill is AUTO and have[f"{skill.name}/VERSION"].decode().strip() != version:
            fail(f"{out.relative_to(ROOT)} carries VERSION {have[f'{skill.name}/VERSION'].decode().strip()}, not {version}")
    print(f"dist zips match skills/ (VERSION {version})")


def packaged(skill):
    """Files that go in dist/<skill>.zip, by their name inside the zip (top-level folder = skill name).
    The installed copy is what bootstrap.sh falls back to when GitHub is unreachable, so it carries every
    script, snippet and reference; the back-test (evals/, run_evals.py) stays in the repo."""
    out = {}
    for f in sorted(skill.rglob("*")):
        rel = f.relative_to(skill)
        if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and f.name != ".DS_Store" \
                and rel.parts[0] != "evals" and f.name != "run_evals.py":
            out[f"{skill.name}/{rel.as_posix()}"] = f
    return out


if __name__ == "__main__":
    main()
