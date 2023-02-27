"""Helper function and script that returns all *.o(bj) paths from a given root path."""

import os
import sys
from pathlib import Path
from typing import List

def listobjs(root: Path) -> List[Path]:
    obj_files: List[Path] = []

    for root, _, files in os.walk(root.absolute()):
        obj_files.extend([Path(root, f) for f in files if f.endswith(".obj") or f.endswith(".o")])

    return obj_files


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <root path to search>")
        sys.exit(1)

    root = Path(sys.argv[1])

    if not os.path.isdir(root.absolute()):
        print(f"Couldn't find path {root.absolute()}")
        sys.exit(1)

    obj_files = listobjs(root)

    for file in obj_files:
        print(file, end=" ")
    print()
