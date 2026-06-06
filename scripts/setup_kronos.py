#!/usr/bin/env python3
"""
Downloads the Kronos model Python source files from GitHub into
models/kronos_src/model/ so the KronosResearchAgent can import them.

Run once before starting the Kronos agent:
    python scripts/setup_kronos.py
"""
import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).parents[1] / "models" / "kronos_src" / "model"

GITHUB_RAW = "https://raw.githubusercontent.com/shiyu-coder/Kronos/master/model"
FILES = ["__init__.py", "kronos.py", "module.py"]


def main():
    DEST.mkdir(parents=True, exist_ok=True)

    for fname in FILES:
        url = f"{GITHUB_RAW}/{fname}"
        dest_path = DEST / fname
        if dest_path.exists():
            print(f"  already exists: {dest_path}")
            continue
        print(f"  downloading {fname} ...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest_path)
            print("ok")
        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    # Write a top-level __init__.py so the directory is a package root
    init = DEST.parent / "__init__.py"
    if not init.exists():
        init.write_text("")

    print(f"\nKronos source ready at: {DEST}")
    print("Model weights will be downloaded automatically on first run from HuggingFace.")
    print("  Tokenizer: NeoQuasar/Kronos-Tokenizer-2k")
    print("  Model:     NeoQuasar/Kronos-mini")


if __name__ == "__main__":
    main()
