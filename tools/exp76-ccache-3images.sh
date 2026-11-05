#!/usr/bin/env bash
# Bash / GitHub Actions Ubuntu 24.04 / three complete ARM64 QEMU_RT Image builds with ccache / NO FLASH
set -Eeuo pipefail
K="$1"; OUT="$2"; REPORT="$3"; LOGS="$4"
mkdir -p "$REPORT" "$LOGS"
test -n "$CCACHE_DIR" && test -n "$CCACHE_BASEDIR" || {
  echo 'BLOCKED_ENV: CCACHE_DIR/CCACHE_BASEDIR required'; exit 2;
}
export CCACHE_COMPILERCHECK=content CCACHE_MAXSIZE=5G
CONFIG_SHA="$(sha256sum "$OUT/.config" | cut -d' ' -f1)"
grep -qx 'CONFIG_PREEMPT_RT_FULL=y' "$OUT/.config"
command -v ccache >/dev/null
command -v clang >/dev/null
# Snapshot existing RT changes first; mutations remain in this disposable CI tree.
git -C "$K" add -u
git -C "$K" -c user.name=EXP76-CI -c user.email=exp76-ci@example.invalid \
  commit -m 'EXP76 RT trial baseline for ccache measurements' \
  > "$LOGS/ccache-baseline-commit.log" 2>&1 || {
    git -C "$K" diff --cached --quiet || {
      cat "$LOGS/ccache-baseline-commit.log"; exit 1;
    }
  }
BASE_SHA="$(git -C "$K" rev-parse HEAD)"
ccache --clear
for PHASE in cold warm_same_commit warm_five_line_commit; do
  if [ "$PHASE" = warm_five_line_commit ]; then
    cat >> "$K/kernel/sched/core.c" <<'EOF'
/* EXP76_CCACHE_DELTA_BEGIN
 * source change confined to scheduler core
 * five-line comment for mutation phase
 * no runtime scheduler behavior altered
 * EXP76_CCACHE_DELTA_END */
EOF
    git -C "$K" add kernel/sched/core.c
    git -C "$K" -c user.name=EXP76-CI -c user.email=exp76-ci@example.invalid \
      commit -m 'EXP76 five-line scheduler comment mutation' \
      > "$LOGS/ccache-mutation-commit.log" 2>&1
    git -C "$K" diff HEAD^ HEAD --numstat > "$REPORT/ccache-mutation-numstat.txt"
    test "$(wc -l < "$REPORT/ccache-mutation-numstat.txt")" -eq 1
  fi
  ccache --zero-stats
  START="$(date +%s%N)"
  if [ "$PHASE" = cold ]; then
    make -C "$K" O="$OUT" ARCH=arm64 \
      CC='ccache clang' LD=ld.lld HOSTCC=gcc OBJCOPY=llvm-objcopy \
      CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
      -j"$(nproc)" Image > "$LOGS/ccache-full-$PHASE.log" 2>&1 || {
        tail -n 80 "$LOGS/ccache-full-$PHASE.log"; exit 1;
      }
  else
    make -B -C "$K" O="$OUT" ARCH=arm64 \
      CC='ccache clang' LD=ld.lld HOSTCC=gcc OBJCOPY=llvm-objcopy \
      CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
      -j"$(nproc)" Image > "$LOGS/ccache-full-$PHASE.log" 2>&1 || {
        tail -n 80 "$LOGS/ccache-full-$PHASE.log"; exit 1;
      }
  fi
  END="$(date +%s%N)"
  test -s "$OUT/arch/arm64/boot/Image"
  test "$(sha256sum "$OUT/.config" | cut -d' ' -f1)" = "$CONFIG_SHA"
  echo "$(( (END-START)/1000000 ))" > "$REPORT/ccache-full-$PHASE.duration_ms"
  ccache --print-stats > "$REPORT/ccache-full-$PHASE.tsv"
  sha256sum "$OUT/arch/arm64/boot/Image" > "$REPORT/ccache-full-$PHASE.image-sha256"
  git -C "$K" rev-parse HEAD > "$REPORT/ccache-full-$PHASE.git-sha"
done
python3 - "$REPORT" "$CONFIG_SHA" "$BASE_SHA" <<'PY'
# Python 3 / GH Actions / summarize actual ccache stats for three full Images
import json
import sys
from pathlib import Path
p=Path(sys.argv[1])
rows=[]
for phase in ("cold","warm_same_commit","warm_five_line_commit"):
    # --print-stats uses stable TSV in ccache 4.x; --show-stats
    # does not accept --format=json in the Ubuntu 24.04 runner.
    raw=(p/f"ccache-full-{phase}.tsv").read_text()
    counts={}
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, sep, value=line.partition("\t")
        if not sep or not value.strip().isdigit() or key in counts:
            raise RuntimeError("invalid ccache TSV counter in "+phase+": "+repr(line))
        counts[key]=int(value)
    for key in ("direct_cache_hit","preprocessed_cache_hit","cache_miss"):
        if key not in counts:
            raise RuntimeError("missing ccache counter in "+phase+": "+key)
    direct=counts["direct_cache_hit"]
    preprocessed=counts["preprocessed_cache_hit"]
    misses=counts["cache_miss"]
    total=direct+preprocessed+misses
    if total==0:
        raise RuntimeError("ccache did not record calls in "+phase+": "+repr(counts))
    rows.append({
        "phase":phase,"git_commit":(p/f"ccache-full-{phase}.git-sha").read_text().strip(),
        "config_sha256":sys.argv[2],
        "duration_s":int((p/f"ccache-full-{phase}.duration_ms").read_text())/1000,
        "direct_hit":direct,"preprocessed_hit":preprocessed,"cache_miss":misses,
        "hit_rate_pct":round(100*(direct+preprocessed)/total,3),
        "image_sha256":(p/f"ccache-full-{phase}.image-sha256").read_text().split()[0]
    })
result={
 "stage":"EXP76_CCACHE_THREE_FULL_ARM64_IMAGES",
 "scope":"FULL_IMAGE_QEMU_RT","source_baseline_commit":sys.argv[3],
 "ccache_runs":rows,"ccache_warm_hit_rate_pct":rows[1]["hit_rate_pct"],
 "ccache_changed_commit_hit_rate_pct":rows[2]["hit_rate_pct"],
 "rt_handoff_ready":False
}
cold_hits=rows[0]["direct_hit"]+rows[0]["preprocessed_hit"]
cold_misses=rows[0]["cache_miss"]
cold_total=cold_hits+cold_misses
# A cleared cache can still record hits later in the same cold build when
# compile requests repeat. Require at least 95% misses, not zero hits.
if cold_total == 0 or cold_misses/cold_total < .95:
    raise RuntimeError("cold baseline exceeds 5% hits; inspect cache clearing")
if rows[1]["hit_rate_pct"] <= 90:
    raise RuntimeError("same-commit warm ccache hit rate <=90%")
if rows[2]["hit_rate_pct"] < 50:
    raise RuntimeError("five-line mutation warm ccache hit rate <50%")
result["cold_cache_expected_miss_rate_min_pct"]=95.0
result["cold_observed_within_build_hits"]=cold_hits
result["cold_zero_hits_strict"]=cold_hits==0
result["changed_core_object_cache_invalidation_verified"]=False
result["qualified_cache_measurement"]="PASS_WARM_THRESHOLDS_WITH_COLD_HITS_AND_NO_CORE_OBJECT_TRACE"
if rows[0]["git_commit"]!=rows[1]["git_commit"]:
    raise RuntimeError("same-commit warm phase used a different source")
if rows[2]["git_commit"]==rows[1]["git_commit"]:
    raise RuntimeError("five-line mutation did not create a new commit")
(p/"ccache-three-full-images.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
PY
