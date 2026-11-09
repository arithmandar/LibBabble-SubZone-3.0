#!/usr/bin/env bash
# Mirror GitHub content to the WoWAce SVN repository (one-way, Git -> SVN).
#
# Steps:
#   1. Baseline check: SVN trunk must still match the Git commit it came from.
#      Stops if anyone changed SVN outside this mirror.
#   2. Trunk sync: copy the target commit's files into a trunk working copy,
#      schedule adds and deletes, and commit once. The commit message ends with
#      "Git commit: <sha>", which is the baseline for the next run.
#   3. Tag: for tag pushes, create tags/<tag> with a server-side svn copy of
#      the trunk revision that holds the tagged commit.
#
# Environment:
#   MODE          dry-run (default) or commit
#   SVN_URL       SVN repository root
#   TARGET_SHA    Git commit to mirror (default: HEAD)
#   GIT_TAG       Tag name when triggered by a tag push (optional)
#   MAIN_REF      Branch that commit mode requires TARGET_SHA to be on
#                 (default: origin/main)
#   SVN_USERNAME, SVN_PASSWORD   Required in commit mode

set -euo pipefail

MODE="${MODE:-dry-run}"
SVN_URL="${SVN_URL:-https://repos.wowace.com/wow/libbabble-subzone-3-0}"
TRUNK="${SVN_URL}/trunk"
TARGET_SHA="$(git rev-parse "${TARGET_SHA:-HEAD}^{commit}")"
GIT_TAG="${GIT_TAG:-}"
MAIN_REF="${MAIN_REF:-origin/main}"
WORK="${RUNNER_TEMP:-/tmp}/svn-mirror"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
SVN=(svn --non-interactive --no-auth-cache)

# Paths that exist only on GitHub and are never mirrored.
EXCLUDES=(.git .github)

case "$MODE" in
	dry-run|commit) ;;
	*) echo "::error::Unknown MODE: $MODE"; exit 1 ;;
esac

rm -rf "$WORK"
mkdir -p "$WORK"

# Write to the job summary and to the log.
say() {
	printf '%s\n' "$*"
	[ "$SUMMARY" = /dev/stdout ] || printf '%s\n' "$*" >>"$SUMMARY"
}
fail() { echo "::error::$*"; say ""; say "**Result: FAILED** — $*"; exit 1; }

# Run an svn command that writes to the repository, passing the password on stdin.
svn_write() {
	printf '%s' "$SVN_PASSWORD" | "${SVN[@]}" --username "$SVN_USERNAME" --password-from-stdin "$@"
}

# Write a Git tree (without excluded paths) into a directory.
git_export() {
	local rev="$1" dest="$2"
	mkdir -p "$dest"
	git archive --format=tar "$rev" | tar -x -C "$dest"
	local p
	for p in "${EXCLUDES[@]}"; do rm -rf "${dest:?}/$p"; done
}

if [ "$MODE" = commit ]; then
	[ -n "${SVN_USERNAME:-}" ] && [ -n "${SVN_PASSWORD:-}" ] || fail "SVN_USERNAME and SVN_PASSWORD are required in commit mode."
	say "## SVN mirror"
else
	say "## SVN mirror (dry run)"
fi
say ""
say "- SVN trunk: \`$TRUNK\`"
say "- Target Git commit: \`$TARGET_SHA\`"
[ -n "$GIT_TAG" ] && say "- Git tag: \`$GIT_TAG\`"

# Only commits on main reach SVN, so a tag on another branch cannot move trunk.
if [ "$MODE" = commit ]; then
	git rev-parse -q --verify "${MAIN_REF}^{commit}" >/dev/null || fail "$MAIN_REF is not available. Check out with fetch-depth: 0."
	git merge-base --is-ancestor "$TARGET_SHA" "$MAIN_REF" || fail "Commit ${TARGET_SHA:0:10} is not on $MAIN_REF. Only commits on main are mirrored."
fi

# ---------------------------------------------------------------------------
# 1. Baseline check
# ---------------------------------------------------------------------------
svn_rev="$("${SVN[@]}" info --show-item last-changed-revision "$TRUNK")"
svn_msg="$("${SVN[@]}" log -l1 "$TRUNK@$svn_rev")"
say "- SVN trunk last changed revision: r$svn_rev"

marker="$(printf '%s\n' "$svn_msg" | sed -n 's/^Git commit: \([0-9a-f]\{40\}\)$/\1/p' | head -n1)"
if [ -n "$marker" ]; then
	base_sha="$marker"
	say "- Baseline: r$svn_rev was mirrored from Git commit \`$base_sha\`"
else
	# No mirror marker yet: fall back to the git-svn import metadata.
	base_sha="$(git log --all --format=%H -F --grep="git-svn-id: ${TRUNK}@${svn_rev} " | head -n1)"
	[ -n "$base_sha" ] || fail "SVN trunk r$svn_rev has no matching Git commit. SVN may have been changed outside the mirror."
	say "- Baseline: r$svn_rev was imported as Git commit \`$base_sha\` (git-svn-id)"
fi
git cat-file -e "${base_sha}^{commit}" 2>/dev/null || fail "Baseline commit $base_sha is not in this repository."

"${SVN[@]}" export -q --ignore-keywords --ignore-externals "$TRUNK@$svn_rev" "$WORK/svn-export"
git_export "$base_sha" "$WORK/git-base"

say ""
say "### Baseline content check"
if diff_out="$(diff -r -q --strip-trailing-cr "$WORK/git-base" "$WORK/svn-export")"; then
	say "SVN trunk r$svn_rev matches Git commit \`${base_sha:0:10}\`."
else
	say '```'
	say "${diff_out//$WORK\//}"
	say '```'
	fail "SVN trunk r$svn_rev does not match Git commit ${base_sha:0:10}. Stopping instead of overwriting SVN changes."
fi

# ---------------------------------------------------------------------------
# 2. Trunk sync
# ---------------------------------------------------------------------------
# The revision that holds the target commit, once known (used for tagging).
target_rev=""
# Set when this run creates (or, in a dry run, would create) a trunk revision.
pending_commit=""

say ""
say "### Trunk sync: \`${base_sha:0:10}\` → \`${TARGET_SHA:0:10}\`"

if [ "$base_sha" = "$TARGET_SHA" ]; then
	target_rev="$svn_rev"
	say "SVN trunk already holds the target commit (r$svn_rev)."
elif git merge-base --is-ancestor "$TARGET_SHA" "$base_sha"; then
	# Target is older than what trunk holds, for example a re-run of an old
	# workflow or a tag on an older commit. Never move trunk backwards.
	say "The target commit is older than SVN trunk. Trunk is left unchanged."
elif ! git merge-base --is-ancestor "$base_sha" "$TARGET_SHA"; then
	fail "The target commit does not descend from the SVN baseline ${base_sha:0:10} (history was rewritten?)."
else
	"${SVN[@]}" checkout -q --ignore-externals "$TRUNK@$svn_rev" "$WORK/wc"
	git_export "$TARGET_SHA" "$WORK/git-target"
	rsync -a --delete --exclude .svn "$WORK/git-target/" "$WORK/wc/"

	# Schedule additions (? and I) and deletions (!). --no-ignore makes SVN
	# take every file Git has, even if svn:ignore matches it. Status lines are
	# "<code><7 columns> <path>", so the path starts at column 9.
	added=0 deleted=0
	while IFS= read -r line; do
		code="${line:0:1}" path="${line:8}"
		case "$code" in
			'?'|'I') (cd "$WORK/wc" && "${SVN[@]}" add -q --parents --force --no-ignore "$path@"); added=$((added + 1)) ;;
			'!') (cd "$WORK/wc" && "${SVN[@]}" rm -q --force "$path@"); deleted=$((deleted + 1)) ;;
			'~') fail "SVN cannot replace '$path' with a different node kind (file vs directory) in one commit." ;;
		esac
	done < <(cd "$WORK/wc" && "${SVN[@]}" status --no-ignore)

	# Keywords are no longer used, so drop the svn:keywords properties.
	if [ -n "$(cd "$WORK/wc" && "${SVN[@]}" propget -R svn:keywords .)" ]; then
		(cd "$WORK/wc" && "${SVN[@]}" propdel -q -R svn:keywords .)
		say "Removed the svn:keywords property from all files."
	fi

	status="$(cd "$WORK/wc" && "${SVN[@]}" status)"
	if [ -z "$status" ]; then
		target_rev="$svn_rev"
		say "No file changes. Only GitHub-only paths changed."
	else
		say "Added $added, deleted $deleted path(s). Full status (\`A\` add, \`M\` modify, \`D\` delete, second column = property change):"
		say '```'
		say "$status"
		say '```'

		msg_file="$WORK/commit-message.txt"
		{
			echo "Mirror GitHub ${GITHUB_REF_NAME:-main} at ${TARGET_SHA:0:10}"
			echo ""
			git log --format='- %h %s' "${base_sha}..${TARGET_SHA}" -- . ':!.github'
			echo ""
			echo "Git commit: $TARGET_SHA"
		} >"$msg_file"
		say ""
		say "SVN commit message:"
		say '```'
		say "$(cat "$msg_file")"
		say '```'

		pending_commit=1
		if [ "$MODE" = commit ]; then
			(cd "$WORK/wc" && svn_write commit -q -F "$msg_file")
			target_rev="$("${SVN[@]}" info --show-item last-changed-revision "$TRUNK")"
			say ""
			say "Committed **r$target_rev** to SVN trunk."
		else
			say ""
			say "Dry run: nothing was committed."
		fi
	fi
fi

# ---------------------------------------------------------------------------
# 3. Tag
# ---------------------------------------------------------------------------
if [ -n "$GIT_TAG" ]; then
	say ""
	say "### Tag \`$GIT_TAG\`"
	if "${SVN[@]}" info "$SVN_URL/tags/$GIT_TAG" >/dev/null 2>&1; then
		fail "SVN tag tags/$GIT_TAG already exists. It is never overwritten."
	fi

	if [ -z "$target_rev" ]; then
		# The tagged commit is older than trunk: find the revision that mirrored it.
		# (No -q: --search needs the log messages.)
		target_rev="$("${SVN[@]}" log --search "Git commit: $TARGET_SHA" "$TRUNK" | sed -n 's/^r\([0-9]*\) | .*/\1/p' | head -n1)"
	fi

	if [ -z "$target_rev" ] && [ -n "$pending_commit" ]; then
		say "Would tag the trunk revision created by this sync."
	elif [ -n "$target_rev" ]; then
		tag_msg="Tag $GIT_TAG

Git commit: $TARGET_SHA"
		if [ "$MODE" = commit ]; then
			svn_write copy -q -m "$tag_msg" "$TRUNK@$target_rev" "$SVN_URL/tags/$GIT_TAG"
			say "Created \`tags/$GIT_TAG\` from trunk@r$target_rev."
		else
			say "Would run: \`svn copy trunk@r$target_rev tags/$GIT_TAG\`"
		fi
	else
		fail "No SVN trunk revision holds Git commit $TARGET_SHA, so tags/$GIT_TAG cannot be created."
	fi
fi

say ""
if [ "$MODE" = commit ]; then
	say "**Result: DONE**"
else
	say "**Result: PASSED (dry run, nothing was committed to SVN)**"
fi
