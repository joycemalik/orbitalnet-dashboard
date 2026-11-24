"""One-click worker for splitting research runs across two laptops.

Laptop B (the helper):  download this one file anywhere, then double-click it
                        or run:  python run_laptop.py
                        It clones the repo, installs everything, runs the
                        laptop_B jobs from research/WORK_SPLIT.json, and pushes
                        the results to branch <branch>-laptopB.
Laptop A (main):        python run_laptop.py --side A          (run A's half)
                        python run_laptop.py --side A --merge  (pull B's results, merge shards)

Options: --dry-run (show what would happen), --skip-tests.
Standard library only, so it runs before anything is installed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/joycemalik/orbitalnet-dashboard.git"
BRANCH = "research/open-world-planner"
SPLIT_FILE = "research/WORK_SPLIT.json"
HERE = Path(__file__).resolve().parent
LOG = None


def say(msg: str) -> None:
    print(msg, flush=True)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def die(msg: str) -> None:
    say("\n*** STOPPED: " + msg)
    if os.name == "nt" and sys.stdin and sys.stdin.isatty():
        input("Press Enter to close...")
    sys.exit(1)


def run(cmd, cwd=None, check=True, capture=False):
    say("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, text=True,
                       capture_output=capture)
    if check and r.returncode != 0:
        die(f"command failed ({r.returncode}): {' '.join(str(c) for c in cmd)}\n{(r.stderr or '') if capture else ''}")
    return r


def out(cmd, cwd=None) -> str:
    return run(cmd, cwd=cwd, capture=True).stdout.strip()


def find_python(want: str) -> list[str]:
    """Return a command that launches Python `want` (e.g. '3.13')."""
    if f"{sys.version_info.major}.{sys.version_info.minor}" == want:
        return [sys.executable]
    if shutil.which("py"):
        r = subprocess.run(["py", f"-{want}", "--version"], capture_output=True, text=True)
        if r.returncode == 0:
            return ["py", f"-{want}"]
    exe = shutil.which(f"python{want}")
    if exe:
        return [exe]
    if os.name == "nt" and shutil.which("winget"):
        say(f"Python {want} not found; installing it with winget...")
        run(["winget", "install", "-e", "--id", f"Python.Python.{want}",
             "--accept-source-agreements", "--accept-package-agreements"], check=False)
        r = subprocess.run(["py", f"-{want}", "--version"], capture_output=True, text=True)
        if r.returncode == 0:
            return ["py", f"-{want}"]
    die(f"Python {want} is required (shards must match exactly). Install it from "
        f"https://www.python.org/downloads/ and run this again.")


def get_repo(side: str, dry: bool) -> Path:
    if (HERE / SPLIT_FILE).exists() and (HERE / ".git").exists():
        return HERE
    if side == "A":
        die("--side A must be run from inside the repo checkout")
    if not shutil.which("git"):
        die("git is not installed. Install from https://git-scm.com/download/win and run again.")
    repo = HERE / "orbitalnet-work"
    if not repo.exists():
        say(f"Cloning into {repo} ...")
        if dry:
            return repo
        run(["git", "clone", REPO_URL, repo])
    run(["git", "fetch", "origin"], cwd=repo)
    return repo


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", choices=("A", "B"), default="B")
    ap.add_argument("--merge", action="store_true", help="side A: fetch B's results and merge shards")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args()
    side, dry = args.side, args.dry_run

    repo = get_repo(side, dry)
    LOG = repo / f"laptop{side}_run.log" if repo.exists() else None
    say(f"=== laptop {side}  repo={repo}")
    if dry and not repo.exists():
        say("(dry run: would clone, install, test, run laptop_B jobs, push)")
        return

    if side == "B":
        split = json.loads(out(["git", "show", f"origin/{BRANCH}:{SPLIT_FILE}"], cwd=repo))
    else:
        split = json.loads((repo / SPLIT_FILE).read_text())
    branch = split["branch"]
    pin = out(["git", "log", "-1", "--format=%H", f"origin/{branch}", "--", SPLIT_FILE], cwd=repo)
    say(f"Pinned code commit (last change of {SPLIT_FILE}): {pin}")
    b_branch = f"{branch}-laptopB"

    if side == "B":
        run(["git", "checkout", "-q", "-B", b_branch, pin], cwd=repo)
    else:
        head = out(["git", "rev-parse", "HEAD"], cwd=repo)
        if head != pin:
            die(f"HEAD is {head}, but laptop B runs {pin}. Shards would not merge. "
                f"Commit/push WORK_SPLIT.json changes last, then run again.")

    if args.merge:
        return merge_from_b(repo, split, b_branch, dry)

    # environment
    py = find_python(split["python"])
    venv = repo / ".venv"
    vpy = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not vpy.exists():
        say("Creating virtual environment...")
        if not dry:
            run(py + ["-m", "venv", venv])
    if not dry:
        run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([vpy, "-m", "pip", "install", "-q", "-r", repo / "research/requirements-research.txt"])
        np_ver = out([vpy, "-c", "import numpy;print(numpy.__version__)"])
        if np_ver != split["numpy"]:
            die(f"numpy {np_ver} installed, need {split['numpy']}")
        if not args.skip_tests:
            say("Running tests (pytest research/) ...")
            run([vpy, "-m", "pytest", "research/", "-q", "-x", "-p", "no:cacheprovider"], cwd=repo)

    jobs = split[f"laptop_{side}"]
    done_outputs = []
    for i, job in enumerate(jobs, 1):
        target = repo / job["output"]
        if target.exists():
            say(f"[{i}/{len(jobs)}] already done: {job['output']}")
            done_outputs.append(job["output"])
            continue
        say(f"[{i}/{len(jobs)}] running -> {job['output']}")
        if not dry:
            run([vpy] + job["cmd"], cwd=repo)
            if not target.exists():
                die(f"job finished but {job['output']} was not written")
            done_outputs.append(job["output"])

    if dry:
        say("(dry run: stopping before commit/push)")
        return

    if side == "B":
        if run(["git", "config", "user.name"], cwd=repo, check=False, capture=True).returncode != 0:
            run(["git", "config", "user.name", "laptop-B"], cwd=repo)
            run(["git", "config", "user.email", "laptop-b@localhost"], cwd=repo)
        run(["git", "add", "--"] + done_outputs, cwd=repo)
        if run(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False).returncode != 0:
            run(["git", "commit", "-q", "-m", f"research: laptop B shard results ({len(done_outputs)} files)"], cwd=repo)
        say("Pushing (a GitHub sign-in window may open the first time)...")
        run(["git", "push", "-u", "origin", b_branch], cwd=repo)
        say(f"\nDONE: {len(done_outputs)} job outputs pushed to {b_branch}.")
    else:
        say(f"\nDONE: {len(done_outputs)} laptop A outputs. When B is finished: python run_laptop.py --side A --merge")
    if os.name == "nt" and sys.stdin and sys.stdin.isatty() and side == "B":
        input("Press Enter to close...")


def merge_from_b(repo: Path, split: dict, b_branch: str, dry: bool) -> None:
    run(["git", "fetch", "origin", b_branch], cwd=repo)
    b_outputs = [j["output"] for j in split["laptop_B"]]
    run(["git", "checkout", f"origin/{b_branch}", "--"] + b_outputs, cwd=repo)
    run(["git", "reset", "-q", "--"] + b_outputs, cwd=repo)  # keep them as plain files; you commit later
    vpy = Path(sys.executable)
    for d in split.get("merge_dirs", []):
        if not dry:
            run([vpy, "-m", "research.experiments.merge_shards", d], cwd=repo)
    say("\nDONE: laptop B results pulled in and shards merged.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("interrupted (safe to rerun; finished jobs are skipped)")
