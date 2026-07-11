function Get-AiQualityStatus {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Owner,
    [string[]]$Repository,
    [switch]$AllRepositories,
    [string]$Latest = $script:DefaultWorkflowRef
  )
  Assert-AiQualityPowerShell
  Assert-GhCli

  $repos = if ($AllRepositories) {
    Invoke-GhJson -Arguments @('repo', 'list', $Owner, '--limit', '1000', '--json', 'name,isArchived,isFork,isEmpty')
  } else {
    foreach ($name in $Repository) {
      Invoke-GhJson -Arguments @('repo', 'view', "$Owner/$name", '--json', 'name,isArchived,isFork,isEmpty')
    }
  }

  foreach ($repo in $repos) {
    $current = 'none'
    try {
      $content = gh api "repos/$Owner/$($repo.name)/contents/.github/workflows/ai-quality.yml" --jq '.content' 2>$null
      if ($LASTEXITCODE -eq 0 -and $content) {
        $decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(($content -join '').Replace("`n", '')))
        $ref = Get-AiQualityWorkflowRef -Content $decoded
        if ($ref) { $current = $ref }
      }
    }
    catch {
      $current = 'none'
    }
    $status = if ($current -eq 'none') { 'Not installed' } elseif ($current -eq $Latest) { 'Current' } else { 'Update available' }
    [pscustomobject]@{
      Repository = $repo.name
      Current = $current
      Latest = $Latest
      Status = $status
    }
  }
}

