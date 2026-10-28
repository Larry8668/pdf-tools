"""The `pdf-tools` dispatcher: overview, help, version and typo suggestions."""

from __future__ import annotations

import subprocess
import sys

import pytest

from pdf_tools.cli import COMMANDS, main


def test_overview_lists_every_command(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    for name in COMMANDS:
        assert name in out


def test_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("pdf-tools ")


def test_unknown_command_suggests_closest(capsys):
    assert main(["mrge"]) == 2
    assert "Did you mean 'merge'" in capsys.readouterr().err


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_every_command_has_help(name):
    # A subprocess, because each tool's argparse exits the interpreter on --help.
    result = subprocess.run(
        [sys.executable, "-m", "pdf_tools.cli", "help", name],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"usage: pdf-tools {name}" in result.stdout
