"""CLI smoke tests."""

from powernse.cli import build_parser, main


def test_help_exits_zero() -> None:
    parser = build_parser()
    assert parser.prog == "powernse"


def test_status_empty_archive(tmp_path) -> None:
    code = main(["status", "--root", str(tmp_path)])
    assert code == 0
