function Update-AiQuality {
  [CmdletBinding(SupportsShouldProcess)]
  param(
    [Parameter(Mandatory)][string]$Owner,
    [string[]]$Repository,
    [switch]$AllRepositories,
    [switch]$CreatePullRequest,
    [string]$TargetRef = $script:DefaultWorkflowRef,
    [string]$WorkDirectory = (Join-Path ([System.IO.Path]::GetTempPath()) 'ai-quality-update'),
    [switch]$DryRun
  )
  Assert-AiQualityPowerShell
  Assert-GhCli
  $statuses = Get-AiQualityStatus -Owner $Owner -Repository $Repository -AllRepositories:$AllRepositories -Latest $TargetRef |
    Where-Object { $_.Status -ne 'Current' }

  New-Item -ItemType Directory -Force -Path $WorkDirectory | Out-Null
  foreach ($status in $statuses) {
    $fullName = "$Owner/$($status.Repository)"
    $branch = 'codex/update-ai-quality'
    if ($PSCmdlet.ShouldProcess($fullName, "AI品質管理を $TargetRef へ更新")) {
      if ($DryRun) {
        [pscustomobject]@{ Repository = $fullName; Status = 'DryRun'; Current = $status.Current; Target = $TargetRef }
        continue
      }
      $local = Join-Path $WorkDirectory $status.Repository
      if (-not (Test-Path -LiteralPath $local)) {
        Invoke-Gh -Arguments @('repo', 'clone', $fullName, $local) | Out-Null
      }
      $defaultBranch = Get-RepositoryDefaultBranch -Owner $Owner -Name $status.Repository
      Push-Location $local
      try {
        git fetch origin | Out-Null
        git switch -C $branch "origin/$defaultBranch" | Out-Null
        $workflow = Join-Path $local '.github/workflows/ai-quality.yml'
        if (-not (Test-Path -LiteralPath $workflow)) {
          Set-AiQualityFiles -RepositoryPath $local -WorkflowRef $TargetRef
        } else {
          $text = Get-Content -LiteralPath $workflow -Raw
          $text = $text -replace 'reusable-quality-gate\.yml@[^\s]+', "reusable-quality-gate.yml@$TargetRef"
          Set-Content -LiteralPath $workflow -Value $text -Encoding utf8NoBOM
        }
        if (-not (git status --short)) {
          [pscustomobject]@{ Repository = $fullName; Status = 'AlreadyCurrent'; Target = $TargetRef }
          continue
        }
        git add .github/workflows/ai-quality.yml .ai-quality.yml | Out-Null
        git commit -m "ci: AI品質管理を$TargetRefへ更新" | Out-Null
        git push -u origin $branch | Out-Null
        if ($CreatePullRequest) {
          Invoke-Gh -Arguments @('pr', 'create', '--repo', $fullName, '--base', $defaultBranch, '--head', $branch, '--title', "ci: AI品質管理を$TargetRefへ更新", '--body', "## 概要`n`nAI品質管理ワークフローの参照を $TargetRef へ更新します。`n`n## 未確認事項`n`nActionsの初回実行結果を確認してください。") | Out-Null
        }
        [pscustomobject]@{ Repository = $fullName; Status = 'PullRequestReady'; Target = $TargetRef }
      }
      finally {
        Pop-Location
      }
    }
  }
}

