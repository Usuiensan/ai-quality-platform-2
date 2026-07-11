function Set-AiQualityRuleset {
  [CmdletBinding(SupportsShouldProcess)]
  param(
    [Parameter(Mandatory)][string]$Owner,
    [Parameter(Mandatory)][string]$Repository,
    [string[]]$RequiredChecks = @(
      'quality/build',
      'quality/test',
      'quality/lint',
      'quality/typecheck',
      'ai/code-review',
      'ai/security-review',
      'ai/final-audit',
      'quality/final-gate'
    ),
    [switch]$DryRun
  )
  Assert-AiQualityPowerShell
  Assert-GhCli
  $body = @{
    name = 'AI Quality Gate'
    target = 'branch'
    enforcement = 'active'
    conditions = @{
      ref_name = @{
        include = @('~DEFAULT_BRANCH')
        exclude = @()
      }
    }
    rules = @(
      @{ type = 'deletion' },
      @{ type = 'non_fast_forward' },
      @{ type = 'pull_request'; parameters = @{ required_approving_review_count = 0; dismiss_stale_reviews_on_push = $false; require_code_owner_review = $false; require_last_push_approval = $false; required_review_thread_resolution = $true } },
      @{ type = 'required_status_checks'; parameters = @{ strict_required_status_checks_policy = $true; required_status_checks = @($RequiredChecks | ForEach-Object { @{ context = $_ } }) } }
    )
  } | ConvertTo-Json -Depth 10 -Compress

  if ($PSCmdlet.ShouldProcess("$Owner/$Repository", 'AI品質管理Rulesetを設定')) {
    if ($DryRun) {
      [pscustomobject]@{ Repository = "$Owner/$Repository"; Status = 'DryRun'; Body = $body }
      return
    }
    $temp = New-TemporaryFile
    try {
      Set-Content -LiteralPath $temp -Value $body -Encoding utf8NoBOM
      Invoke-Gh -Arguments @('api', "--method", 'POST', "repos/$Owner/$Repository/rulesets", '--input', $temp.FullName) | Out-Null
      [pscustomobject]@{ Repository = "$Owner/$Repository"; Status = 'RulesetCreated' }
    }
    finally {
      Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
  }
}

