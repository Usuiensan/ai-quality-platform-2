function New-AiManagedRepo {
  [CmdletBinding(SupportsShouldProcess)]
  param(
    [Parameter(Mandatory)][string]$Name,
    [ValidateSet('Public', 'Private', 'Internal')][string]$Visibility = 'Private',
    [ValidateSet('Generic', 'Python', 'Node', 'PowerShell', 'Go', 'Rust')][string]$Preset = 'Generic',
    [string]$Description = '',
    [string]$Owner = '',
    [string]$CloneDirectory = (Get-Location).Path,
    [string]$PlatformRepository = $script:DefaultPlatformRepository,
    [string]$WorkflowRef = $script:DefaultWorkflowRef,
    [switch]$SkipRuleset,
    [switch]$DryRun
  )
  Assert-AiQualityPowerShell
  Assert-GhCli
  Invoke-Gh -Arguments @('auth', 'status') -DryRun:$DryRun | Out-Null

  $repoName = if ($Owner) { "$Owner/$Name" } else { $Name }
  $visibilityArg = "--$($Visibility.ToLowerInvariant())"
  if ($PSCmdlet.ShouldProcess($repoName, 'GitHubリポジトリを作成してAI品質管理を導入')) {
    Invoke-Gh -Arguments @('repo', 'create', $repoName, $visibilityArg, '--description', $Description, '--confirm') -DryRun:$DryRun | Out-Null
    if ($DryRun) {
      return [pscustomobject]@{ Repository = $repoName; Status = 'DryRun'; Next = 'gh repo create と初期pushを実行予定です。' }
    }

    $target = Join-Path $CloneDirectory $Name
    if (-not (Test-Path -LiteralPath $target)) {
      Invoke-Gh -Arguments @('repo', 'clone', $repoName, $target) | Out-Null
    }
    Set-AiQualityFiles -RepositoryPath $target -Preset $Preset -PlatformRepository $PlatformRepository -WorkflowRef $WorkflowRef -Force

    Push-Location $target
    try {
      git branch -M main | Out-Null
      git add . | Out-Null
      git commit -m 'chore: AI品質管理の初期設定を追加' | Out-Null
      git push -u origin main | Out-Null
      if (-not $SkipRuleset) {
        Set-AiQualityRuleset -Owner ($repoName.Split('/')[0]) -Repository ($repoName.Split('/')[-1]) -DryRun:$DryRun | Out-Null
      }
    }
    finally {
      Pop-Location
    }
    [pscustomobject]@{ Repository = $repoName; Status = 'Created'; Path = $target }
  }
}
