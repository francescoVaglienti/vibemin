from vibemin.cli import _parser


def test_reduce_tests_alias_enables_test_reduction() -> None:
    args = _parser().parse_args(["--reduce-tests", "--check", "true"])

    assert args.allow_test_changes is True


def test_feature_base_and_exact_base_are_mutually_exclusive() -> None:
    parser = _parser()

    try:
        parser.parse_args(["--feature-base", "origin/main", "--base", "HEAD~1", "--check", "true"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("mutually exclusive baseline options were accepted")
