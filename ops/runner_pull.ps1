param(
    [string]$MainBranch = "main"
)

$ErrorActionPreference = "Stop"

$status = git status --porcelain
if ($status) {
    throw "Working tree not clean. Commit or stash changes before pull."
}

git fetch --prune origin
git switch $MainBranch
git pull --ff-only origin $MainBranch
