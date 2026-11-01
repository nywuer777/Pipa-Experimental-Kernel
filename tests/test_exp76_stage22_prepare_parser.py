#!/usr/bin/env python3
# Python 3 / Ubuntu CI / EXP76 Stage22 diagnostic report regression / NO FLASH
"""Test report parser using synthetic prepare failures and mixed object results."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools' / 'exp76-stage18-clang21-object-diagnostic.sh'
OBJECTS = ('kernel_sched_cpupri.o', 'kernel_sched_core.o', 'kernel_fork.o')


def parser() -> str:
    contents = SCRIPT.read_text(encoding='utf-8')
    marker = "python3 - \"$REPORT\" <<'PY'\n"
    assert contents.count(marker) == 1, 'report parser marker drift'
    return contents.split(marker, 1)[1].split('\nPY\n', 1)[0]


def check_case(prep_rc: int, codes: tuple[int, ...] | None) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch)
        (out / 'prepare.rc').write_text(str(prep_rc) + '\n')
        (out / 'prepare.errors.txt').write_text('prepare.c:3: error: fixture failure\n' if prep_rc else '')
        for i, obj in enumerate(OBJECTS):
            (out / (obj + '.errors.txt')).write_text('object.c:8: error: fixture failure\n' if codes and codes[i] else '')
            if codes is None:
                (out / (obj + '.skipped')).write_text('BLOCKED_BY_PREPARE\n')
            else:
                (out / (obj + '.rc')).write_text(str(codes[i]) + '\n')
        run = subprocess.run([sys.executable, '-c', parser(), str(out)], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        data = json.loads((out / 'OBJECT_DIAGNOSTIC.json').read_text())
        assert data['preparation']['exit_code'] == prep_rc
        assert data['preparation']['completed'] == (prep_rc == 0)
        assert data['flash_ready'] is False and data['kernel_built'] is False
        for i, obj in enumerate(OBJECTS):
            target = data['targets'][obj]
            if codes is None:
                assert target['attempted'] is False
                assert target['exit_code'] is None
                assert target['compiled'] is False
                assert target['skip_reason'] == 'BLOCKED_BY_PREPARE'
            else:
                assert target['attempted'] is True
                assert target['exit_code'] == codes[i]
                assert target['compiled'] == (codes[i] == 0)
                assert target['skip_reason'] is None
        assert data['all_target_objects_compiled'] == (codes is not None and all(rc == 0 for rc in codes))


def main() -> None:
    check_case(2, None)
    check_case(0, (0, 2, 1))
    check_case(0, (0, 0, 0))
    print('EXP76_STAGE22_REPORT_PARSER=3_PASS; KERNEL_BUILT=false; FLASH_READY=false')


if __name__ == '__main__':
    main()
