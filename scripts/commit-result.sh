#!/usr/bin/env bash
# Bash / GitHub Actions runner / EXP76 incremental evidence publisher
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
mkdir -p "$repo_root/reports"
run_id="${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
result_branch="exp76-rt-h2-result"
result_worktree="${RUNNER_TEMP:?RUNNER_TEMP is required}/exp76-rt-h2-result"
label="${1:-checkpoint}"
lock_file="${RUNNER_TEMP}/exp76-result-publish-${run_id}.lock"
exec 9>"$lock_file"
flock 9

git -C "$repo_root" config user.email "ci@exp76.invalid"
git -C "$repo_root" config user.name "EXP76-CI"
git -C "$repo_root" fetch origin \
  "+refs/heads/$result_branch:refs/remotes/origin/$result_branch" \
  >/dev/null 2>&1 || true

if git -C "$repo_root" show-ref --verify --quiet "refs/remotes/origin/$result_branch"; then
  base_ref="refs/remotes/origin/$result_branch"
else
  base_ref="${GITHUB_SHA:?GITHUB_SHA is required}"
fi

if [[ -e "$result_worktree/.git" ]]; then
  git -C "$result_worktree" reset --hard "$base_ref" >/dev/null
else
  mkdir -p "$(dirname "$result_worktree")"
  git -C "$repo_root" worktree add --detach "$result_worktree" "$base_ref" >/dev/null
fi

result_dir="$result_worktree/exp76-results/$run_id"
mkdir -p "$result_dir"
cp -a "$repo_root/reports/." "$result_dir/"
git -C "$result_worktree" add -A -- "exp76-results/$run_id"
if git -C "$result_worktree" diff --cached --quiet; then
  exit 0
fi

git -C "$result_worktree" commit -m "checkpoint: $run_id $label" >/dev/null
git -C "$result_worktree" push origin "HEAD:refs/heads/$result_branch"
