"""Verify that avstack.py generates the same output as avstack.pl."""

import os
import subprocess
from pathlib import Path
from typing import List

import pytest

from avstack.listobjs import listobjs

if os.name == "nt":
    pytest.skip(allow_module_level=True)


def test_ZSWatch():
    object_file_args = [o.absolute() for o in listobjs(Path("tests/fixtures/ZSWatch/build"))]

    command = [
        "port/avstack.pl",
        "tests/fixtures/ZSWatch/objdump",
        *object_file_args,
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    original = process.stdout.decode("utf-8")

    command = [
        "python3",
        "-m",
        "port.avstack",
        "tests/fixtures/ZSWatch/objdump",
        *object_file_args,
    ]
    process = subprocess.run(command, stdout=subprocess.PIPE)
    port = process.stdout.decode("utf-8")

    def get_table_from_stdout(output: str) -> List[str]:
        lines = output.splitlines()

        # iterate until the beginning of the table
        line = ""
        i = 0
        while line != "------------------------------------------------------------------------":
            line = lines[i]
            i += 1

        # iterate to the end of the table
        out = []
        while line != "The following functions were not resolved:":
            line = lines[i]
            out.append(line)
            i += 1

        return out

    # in cases where cost is the same, avstack.pl and avstack.py may sort differently
    original_table = sorted(get_table_from_stdout(original))
    port_table = sorted(get_table_from_stdout(port))

    assert original_table == port_table
