#!/usr/bin/env python3
"""Create only synthetic /proc/config.gz fixtures from the published EXP06 .config."""
import gzip
import sys
import zipfile
from pathlib import Path

artifact = Path(sys.argv[1])
target = Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(artifact) as z:
    data = z.read("exp06-work/out/.config")
assert b"CONFIG_KSU=y" in data
assert b"CONFIG_PIPA_EXP_SUGOV=y" in data
same = target / "synthetic-identical-config.gz"
different = target / "synthetic-different-config.gz"
with gzip.open(same, "wb", compresslevel=9) as f:
    f.write(data)
changed = data.replace(b"CONFIG_KSU=y", b"# CONFIG_KSU is not set", 1)
changed = changed.replace(b"CONFIG_PIPA_EXP_SUGOV=y", b"# CONFIG_PIPA_EXP_SUGOV is not set", 1)
with gzip.open(different, "wb", compresslevel=9) as f:
    f.write(changed)
print("Generated two synthetic config fixtures (no device data).")
