function Enable-AiQuality {
  [CmdletBinding(SupportsShouldProcess)]
  param(
    [Parameter(Mandatory)][string]$Owner,
    [string[]]$Repository,
    [switch]$AllRepositories,
    [switch]$ExcludeArchived,
    [switch]$ExcludeForks,
    [switch]$CreatePullRequest,
    [ValidateSet('Generic', 'Python', 'Node', 'PowerShell', 'Go', 'Rust')][string]$Preset = 'Generic',
    [string]$WorkDirectory = (Join-Path ([System.IO.Path]::GetTempPath()) 'ai-quality-onboarding'),
    [string]$PlatformRepository = $script:DefaultPlatformRepository,
    [string]$WorkflowRef = $script:DefaultWorkflowRef,
    [switch]$DryRun
  )
  Assert-AiQualityPowerShell
  Assert-GhCli

  $repos = if ($AllRepositories) {
    Invoke-GhJson -Arguments @('repo', 'list', $Owner, '--limit', '1000', '--json', 'name,isArchived,isFork,isEmpty,defaultBranchRef')
  } else {
    foreach ($name in $Repository) {
      Invoke-GhJson -Arguments @('repo', 'view', "$Owner/$name", '--json', 'name,isArchived,isFork,isEmpty,defaultBranchRef')
    }
  }

  New-Item -ItemType Directory -Force -Path $WorkDirectory | Out-Null
  foreach ($repo in $repos) {
    if ($ExcludeArchived -and $repo.isArchived) { continue }
    if ($ExcludeForks -and $repo.isFork) { continue }
    if ($repo.isEmpty) { continue }

    $fullName = "$Owner/$($repo.name)"
    $local = Join-Path $WorkDirectory $repo.name
    $branch = 'codex/enable-ai-quality'
    if ($PSCmdlet.ShouldProcess($fullName, 'AI品質管理の導入PRを作成')) {
      if ($DryRun) {
        [pscustomobject]@{ Repository = $fullName; Status = 'DryRun'; Branch = $branch }
        continue
      }
      if (-not (Test-Path -LiteralPath $local)) {
        Invoke-Gh -Arguments @('repo', 'clone', $fullName, $local) | Out-Null
      }
      Push-Location $local
      try {
        git fetch origin | Out-Null
        git switch -C $branch "origin/$($repo.defaultBranchRef.name)" | Out-Null
        Set-AiQualityFiles -RepositoryPath $local -Preset $Preset -PlatformRepository $PlatformRepository -WorkflowRef $WorkflowRef
        if (-not (git status --short)) {
          [pscustomobject]@{ Repository = $fullName; Status = 'AlreadyInstalled'; Branch = $branch }
          continue
        }
        git add .ai-quality.yml .github/workflows/ai-quality.yml .github/pull_request_template.md | Out-Null
        git commit -m 'ci: AI品質管理ワークフローを導入' | Out-Null
        git push -u origin $branch | Out-Null
        if ($CreatePullRequest) {
          Invoke-Gh -Arguments @('pr', 'create', '--repo', $fullName, '--base', $repo.defaultBranchRef.name, '--head', $branch, '--title', 'ci: AI品質管理ワークフローを導入', '--body', "## 概要`n`nAI品質管理ワークフローと設定ファイルを導入します。`n`n## 動作確認`n`n- [ ] GitHub Actionsで品質ゲートが起動する`n`n## リスク`n`n初回導入のため、必須チェック化は別途Rulesetで確認してください。") | Out-Null
        }
        [pscustomobject]@{ Repository = $fullName; Status = 'PullRequestReady'; Branch = $branch }
      }
      finally {
        Pop-Location
      }
    }
  }
}

