from __future__ import annotations

import argparse
import subprocess
import sys


def run_cmd(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Task runner for word-vault.")
    parser.add_argument(
        "step",
        choices=["init", "test", "lint", "check"],
        help="Task to run.",
    )
    args = parser.parse_args()

    if args.step == "init":
        return run_cmd(["uv", "run", "word-vault", "init-db"])
    if args.step == "test":
        return run_cmd(["uv", "run", "pytest"])
    if args.step == "lint":
        return run_cmd(["uv", "run", "ruff", "check", "."])

    lint_code = run_cmd(["uv", "run", "ruff", "check", "."])
    if lint_code != 0:
        return lint_code
    return run_cmd(["uv", "run", "pytest"])


if __name__ == "__main__":
    sys.exit(main())
