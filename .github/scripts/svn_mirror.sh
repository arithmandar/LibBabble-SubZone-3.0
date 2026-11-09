#!/usr/bin/env bash
# Mirror GitHub content to the WoWAce SVN repository.
#
# This version is DRY RUN ONLY. It never commits to SVN. It:
#   1. Checks that SVN trunk has not changed outside this mirror (baseline check).
#   2. Previews what a sync of the target Git commit would add, modify, or delete.
#   3. For tag pushes, previews the SVN tag that would be created.
#
# Environment:
#   SVN_URL      SVN repository root (default: the LibBabble-SubZone-3.0 repo)
#   TARGET_SHA   Git commit to mirror (default: HEAD)
#   GIT_TAG      Tag name when triggered by a tag push (optional)

set -euo pipefail

SVN_URL="${SVN_URL:-https://repos.wowace.com/wow/libbabble-subzone-3-0}"
TRUNK="${SVN_URL}/trunk"
TARGET_SHA="$(git rev-parse "${TARGET_SHA:-HEAD}")"
GIT_TAG="${GIT_TAG:-}"
WORK="${RUNNER_TEMP:-/tmp}/svn-mirror"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
SVN=(svn --non-interactive --no-auth-cache)

# Paths that exist only on GitHub and are never mirrored.
EXCLUDES=(.git .github)

rm -rf "$WORK"
mkdir -p "$WORK"

# Write to the job summary and to the log.
say() {
	printf '%s\n' "$*"
	[ "$SUMMARY" = /dev/stdout ] || printf '%s\n' "$*" >>"$SUMMARY"
}
fail() { echo "::error::$*"; say ""; say "**Result: FAILED** — $*"; exit 1; }

# Write a Git tree (without excluded paths) into a directory.
git_export() {
	local rev="$1" dest="$2"
	mkdir -p "$dest"
	git archive --format=tar "$rev" | tar -x -C "$dest"
	local p
	for p in "${EXCLUDES[@]}"; do rm -rf "${dest:?}/$p"; done
}

say "## SVN mirror dry run"
say ""
say "- SVN trunk: \`$TRUNK\`"
say "- Target Git commit: \`$TARGET_SHA\`"
[ -n "$GIT_TAG" ] && say "- Git tag: \`$GIT_TAG\`"

# ---------------------------------------------------------------------------
# 1. Baseline check: find the Git commit that matches current SVN trunk.
# ---------------------------------------------------------------------------
svn_rev="$("${SVN[@]}" info --show-item last-changed-revision "$TRUNK")"
svn_msg="$("${SVN[@]}" log -l1 "$TRUNK@$svn_rev")"
say "- SVN trunk last changed revision: r$svn_rev"

base_sha=""
marker="$(printf '%s\n' "$svn_msg" | sed -n 's/^Git commit: \([0-9a-f]\{40\}\)$/\1/p' | head -n1)"
if [ -n "$marker" ]; then
	base_sha="$marker"
	say "- Baseline: r$svn_rev was mirrored from Git commit \`$base_sha\`"
else
	# No mirror marker yet: fall back to the git-svn import metadata.
	base_sha="$(git log --all --format=%H -F --grep="/trunk@${svn_rev} " | head -n1)"
	[ -n "$base_sha" ] || fail "SVN trunk r$svn_rev has no matching Git commit. SVN may have been changed outside the mirror."
	say "- Baseline: r$svn_rev was imported as Git commit \`$base_sha\` (git-svn-id)"
fi
git cat-file -e "${base_sha}^{commit}" 2>/dev/null || fail "Baseline commit $base_sha is not in this repository."

"${SVN[@]}" export -q --ignore-keywords --ignore-externals "$TRUNK@$svn_rev" "$WORK/svn-export"
git_export "$base_sha" "$WORK/git-base"

say ""
say "### Baseline content check"
if diff_out="$(diff -r -q --strip-trailing-cr "$WORK/git-base" "$WORK/svn-export")"; then
	say "SVN trunk r$svn_rev matches Git commit \`${base_sha:0:10}\` (line endings ignored)."
else
	say "SVN trunk r$svn_rev differs from Git commit \`${base_sha:0:10}\`:"
	say '```'
	say "${diff_out//$WORK\//}"
	say '```'
	fail "SVN trunk content does not match the baseline commit."
fi

if eol_out="$(diff -r -q "$WORK/git-base" "$WORK/svn-export")"; then
	say "Line endings also match exactly."
else
	say ""
	say "Note: these files match only after ignoring line endings:"
	say '```'
	say "${eol_out//$WORK\//}"
	say '```'
fi

say ""
say "### SVN properties on trunk"
props="$("${SVN[@]}" proplist -R -v "$TRUNK@$svn_rev" || true)"
if [ -n "$props" ]; then
	say '```'
	say "$props"
	say '```'
else
	say "None."
fi

# ---------------------------------------------------------------------------
# 2. Preview the sync of the target commit into a trunk working copy.
# ---------------------------------------------------------------------------
"${SVN[@]}" checkout -q --ignore-externals "$TRUNK@$svn_rev" "$WORK/wc"
git_export "$TARGET_SHA" "$WORK/git-target"
rsync -a --delete --exclude .svn "$WORK/git-target/" "$WORK/wc/"

status="$("${SVN[@]}" status "$WORK/wc" | sed "s#$WORK/wc/##")"

say ""
say "### Sync preview: \`${base_sha:0:10}\` → \`${TARGET_SHA:0:10}\`"
if [ -z "$status" ]; then
	say "No changes. SVN trunk is already up to date with the target commit."
else
	added="$(printf '%s\n' "$status" | grep -c '^?' || true)"
	modified="$(printf '%s\n' "$status" | grep -c '^M' || true)"
	deleted="$(printf '%s\n' "$status" | grep -c '^!' || true)"
	say "Would add $added, modify $modified, and delete $deleted path(s). (\`?\` = add, \`M\` = modify, \`!\` = delete)"
	say '```'
	say "$status"
	say '```'
	say ""
	say "Planned SVN commit message:"
	say '```'
	say "Mirror GitHub ${GITHUB_REF_NAME:-main} at ${TARGET_SHA:0:10}"
	say ""
	say "$(git log --format='- %h %s' "${base_sha}..${TARGET_SHA}" -- . ':!.github')"
	say ""
	say "Git commit: $TARGET_SHA"
	say '```'
fi

# ---------------------------------------------------------------------------
# 3. Tag preview.
# ---------------------------------------------------------------------------
if [ -n "$GIT_TAG" ]; then
	say ""
	say "### Tag preview"
	if "${SVN[@]}" info "$SVN_URL/tags/$GIT_TAG" >/dev/null 2>&1; then
		say "SVN tag \`tags/$GIT_TAG\` already exists. A real run would stop here instead of overwriting it."
	else
		say "Would run: \`svn copy trunk@<new revision> tags/$GIT_TAG\`"
	fi
fi

say ""
say "**Result: PASSED (dry run, nothing was committed to SVN)**"
