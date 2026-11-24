# Instructions for the coding agent on laptop B (Antigravity / Copilot / human)

You are helping finish a batch of research simulation runs. Laptop A runs half of them and you run the other half.
**Your only job is to run one script and get it to finish.**

## Do this
1. Open a terminal in an empty folder, e.g. `C:\work`.
2. Download the script:
   ```
   curl -L -o run_laptop.py https://raw.githubusercontent.com/joycemalik/orbitalnet-dashboard/research/open-world-planner/run_laptop.py
   ```
3. Run it:
   ```
   python run_laptop.py
   ```
   It does everything: checks git, installs Python 3.13 if missing, clones the repo, creates `.venv`, installs pinned packages, runs the tests, runs the laptop-B jobs, and pushes results to branch `research/open-world-planner-laptopB`.
4. When it prints `DONE: ... pushed to ...`, report that line back. You're finished.

To preview without running anything: `python run_laptop.py --dry-run`.
If it stops halfway, just run it again. Finished jobs are skipped.

## Allowed if it fails
- Install missing tools: Git (https://git-scm.com/download/win), Python **3.13** exactly.
- Fix network, proxy or pip install errors.
- Complete the GitHub sign-in when `git push` asks. The account needs push access to `joycemalik/orbitalnet-dashboard`.

## NOT allowed (this would make the research results invalid)
- Do not edit any `.py` file under `research/`, or `research/WORK_SPLIT.json`.
- Do not change seeds, arguments, package versions or the Python version.
- Do not edit, create or delete anything in `research/results/` by hand.
- Do not run `--split test` or any command not in the laptop_B list.
- Do not push to any branch except `research/open-world-planner-laptopB`.

If tests fail, or a job crashes inside research code, **stop and report the full error**. Don't try to fix the code.
