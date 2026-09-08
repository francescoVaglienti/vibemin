"""Command-line interface for vibemin."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from vibemin import __version__
from vibemin.git import GitError
from vibemin.reducer import Attempt, VerificationError, minimize


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibemin",
        description="Remove unnecessary lines from an AI-generated Git diff, guarded by tests.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="only minimize these repository-relative files/directories (default: all changes)",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="append",
        required=True,
        metavar="COMMAND",
        help="non-mutating test, lint, typecheck, or style command; repeatable",
    )
    parser.add_argument(
        "-p",
        "--preserve-output",
        action="append",
        default=[],
        metavar="COMMAND",
        help="require deterministic command output to remain exactly unchanged; repeatable",
    )
    parser.add_argument(
        "--final-check",
        action="append",
        default=[],
        metavar="COMMAND",
        help="run a non-mutating clean-install or broad validation once on the final candidate",
    )
    parser.add_argument(
        "--security-check",
        action="append",
        default=[],
        metavar="COMMAND",
        help="security-specific oracle required for auth, tenant, token, or secret changes",
    )
    parser.add_argument(
        "--test-strength-check",
        action="append",
        default=[],
        metavar="COMMAND",
        help="mutation or equivalent test-strength oracle required when minimizing tests",
    )
    parser.add_argument(
        "--dependency-check",
        action="append",
        default=[],
        metavar="COMMAND",
        help="manifest/lock consistency oracle required when minimizing dependency files",
    )
    parser.add_argument(
        "--allow-test-changes",
        "--reduce-tests",
        dest="allow_test_changes",
        action="store_true",
        help="allow test reduction (requires a test-strength or preserved-output guard)",
    )
    parser.add_argument(
        "--allow-dependency-changes",
        action="store_true",
        help="allow manifest/lock reduction (requires --dependency-check)",
    )
    parser.add_argument(
        "--allow-visual-changes",
        action="store_true",
        help="allow stylesheet/asset reduction (requires deterministic --preserve-output)",
    )
    parser.add_argument(
        "--allow-untyped-typescript",
        action="store_true",
        help="allow TypeScript reduction without a tsc/typecheck command",
    )
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument(
        "--base",
        default=None,
        help="baseline commit or ref (default: HEAD)",
    )
    baseline.add_argument(
        "--feature-base",
        metavar="REF",
        help="minimize the whole feature since its merge-base with REF",
    )
    parser.add_argument(
        "--timeout", type=float, default=300, help="seconds allowed per command (default: 300)"
    )
    parser.add_argument(
        "--max-attempts", type=int, default=500, help="maximum candidate checks (default: 500)"
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        metavar="SECONDS",
        help="stop searching after this long and finish with the best verified candidate",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="find the minimum but do not change the checkout"
    )
    parser.add_argument("--verbose", action="store_true", help="show failed-command output")
    return parser


def _reporter(verbose: bool):
    def report(attempt: Attempt) -> None:
        status = "PASS" if attempt.passed else "fail"
        print(
            f"[{attempt.number:03}] {status:4}  retained={attempt.retained_units:<5} "
            f"{attempt.seconds:.2f}s",
            file=sys.stderr,
        )
        if verbose and attempt.output:
            print(attempt.output.rstrip(), file=sys.stderr)

    return report


def _raise_interrupt(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    signal.signal(signal.SIGTERM, _raise_interrupt)
    try:
        result = minimize(
            args.check,
            base=args.base or "HEAD",
            feature_base=args.feature_base,
            paths=args.paths,
            preserve_outputs=args.preserve_output,
            final_checks=args.final_check,
            security_checks=args.security_check,
            test_strength_checks=args.test_strength_check,
            dependency_checks=args.dependency_check,
            allow_test_changes=args.allow_test_changes,
            allow_dependency_changes=args.allow_dependency_changes,
            allow_visual_changes=args.allow_visual_changes,
            allow_untyped_typescript=args.allow_untyped_typescript,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
            time_budget=args.time_budget,
            apply=not args.dry_run,
            progress=_reporter(args.verbose),
        )
    except (GitError, VerificationError, ValueError) as error:
        print(f"vibemin: error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(
            "vibemin: interrupted; the checkout was not changed. "
            "Use --time-budget to stop on time with a verified partial result.",
            file=sys.stderr,
        )
        return 130

    action = "Would remove" if args.dry_run else "Removed"
    print(
        f"{action} {result.removed_units} of {result.original_units} diff units "
        f"in {result.attempts} checks; {result.retained_units} remain."
    )
    if result.stopped_early:
        print(
            f"Search stopped early: {result.stopped_early}; "
            "the result is verified but not proven minimal."
        )
    if result.changed_files:
        print("Files simplified:")
        for path in result.changed_files:
            print(f"  {path.as_posix()}")
    else:
        print("The patch was already minimal under these checks.")
    if result.protected_files:
        print("Protected as fixed context:")
        for path, kind in result.protected_files:
            print(f"  {path.as_posix()} ({kind.value})")
    return 0
