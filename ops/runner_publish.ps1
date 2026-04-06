param(
    [string]$RunnerBranch = "runner/Thomas"
)

$ErrorActionPreference = "Stop"

git switch $RunnerBranch
git status --short
git push -u origin $RunnerBranch
