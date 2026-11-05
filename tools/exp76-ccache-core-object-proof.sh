#!/usr/bin/env bash
# Bash / GitHub Actions Ubuntu 24.04 / E404 PREEMPT_RT Clang21 / core.o semantic cache invalidation / NO FLASH
set -Eeuo pipefail
K="$1"; OUT="$2"; REPORT="$3"; LOGS="$4"
mkdir -p "$REPORT" "$LOGS"
export CCACHE_DIR="$REPORT/ccache-core-isolated"
export CCACHE_COMPILERCHECK=content
export CCACHE_BASEDIR="$GITHUB_WORKSPACE"
export CCACHE_MAXSIZE=1G
mkdir -p "$CCACHE_DIR"
command -v ccache >/dev/null
command -v clang >/dev/null
grep -qx 'CONFIG_PREEMPT_RT_FULL=y' "$OUT/.config"
SOURCE="$K/kernel/sched/core.c"
OBJ="$OUT/kernel/sched/core.o"
test -f "$SOURCE"
source_before="$(sha256sum "$SOURCE" | cut -d ' ' -f1)"
config_sha="$(sha256sum "$OUT/.config" | cut -d ' ' -f1)"
ccache --clear
for phase in baseline semantic_mutation semantic_repeat; do
  if [ "$phase" = semantic_mutation ]; then
    cat >> "$SOURCE" <<'MUTATION'
/* EXP76 diagnostic-only semantic codegen mutation; outside flash source. */
static const unsigned long exp76_ccache_semantic_probe
  __attribute__((used)) = 0x76cace14UL;
MUTATION
    source_after="$(sha256sum "$SOURCE" | cut -d ' ' -f1)"
    test "$source_after" != "$source_before"
  fi
  rm -f "$OBJ"
  ccache --zero-stats
  set +e
  make -C "$K" O="$OUT" ARCH=arm64 \
    CC='ccache clang' LD=ld.lld HOSTCC=gcc OBJCOPY=llvm-objcopy \
    CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
    -j2 kernel/sched/core.o > "$LOGS/ccache-core-$phase.log" 2>&1
  rc=$?
  set -e
  echo "$rc" > "$REPORT/ccache-core-$phase.exit"
  if [ "$rc" -ne 0 ]; then
    grep -n -m30 -E 'error:|fatal error:|No rule to make target' "$LOGS/ccache-core-$phase.log" || true
    tail -n 100 "$LOGS/ccache-core-$phase.log"
    exit "$rc"
  fi
  test -s "$OBJ"
  sha256sum "$OBJ" > "$REPORT/ccache-core-$phase.sha256"
  ccache --print-stats > "$REPORT/ccache-core-$phase.tsv"
  grep -q 'kernel/sched/core.o' "$LOGS/ccache-core-$phase.log" || {
    echo "BLOCKED: no scheduler core object compile in $phase"
    exit 3
  }
done
test "$(sha256sum "$OUT/.config" | cut -d ' ' -f1)" = "$config_sha"
python3 - "$REPORT" "$source_before" "$source_after" "$config_sha" <<'PY'
# Python 3 / GitHub Actions / validate miss for semantic source change and hit for repeat / core.o
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
def read(phase):
  data={}
  for line in (p/f"ccache-core-{phase}.tsv").read_text().splitlines():
    key,sep,value=line.partition("\t")
    if sep and value.strip().isdigit():
      data[key]=int(value)
  for key in ("cache_miss","direct_cache_hit","preprocessed_cache_hit"):
    if key not in data:
      raise RuntimeError(f"missing {key}: {phase}")
  sha=(p/f"ccache-core-{phase}.sha256").read_text().split()[0]
  return {"cache_miss":data["cache_miss"],"direct_cache_hit":data["direct_cache_hit"],
          "preprocessed_cache_hit":data["preprocessed_cache_hit"],"object_sha256":sha,
          "compiler_exit_code":int((p/f"ccache-core-{phase}.exit").read_text())}
b=read("baseline");m=read("semantic_mutation");r=read("semantic_repeat")
status="PASS" if (
  b["cache_miss"]>=1 and m["cache_miss"]>=1
  and m["object_sha256"]!=b["object_sha256"]
  and r["cache_miss"]==0
  and r["direct_cache_hit"]+r["preprocessed_cache_hit"]>=1
  and r["object_sha256"]==m["object_sha256"]
) else "FAIL"
report={"stage":"EXP76_CCACHE_REAL_CORE_OBJECT_SEMANTIC_INVALIDATION",
"status":status,"source_sha256_before":sys.argv[2],
"source_sha256_after":sys.argv[3],"config_sha256":sys.argv[4],
"baseline":b,"semantic_mutation":m,"semantic_repeat":r,
"initial_cache_cleared":True,"kernel_object":"kernel/sched/core.o",
"mutation":"appended static const __attribute__((used)) forcing object content change",
"rt_handoff_ready":False}
(p/"ccache-core-object-proof.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
if status!="PASS":raise SystemExit(2)
PY
