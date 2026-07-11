function Test-AiQuality {
  [CmdletBinding()]
  param(
    [string]$Path = (Get-Location).Path
  )
  Assert-AiQualityPowerShell
  $root = Resolve-Path -LiteralPath $Path
  $required = @(
    '.ai-quality.yml',
    '.github/workflows/ai-quality.yml',
    '.github/pull_request_template.md'
  )
  $results = foreach ($file in $required) {
    $fullPath = Join-Path $root $file
    [pscustomobject]@{
      File = $file
      Exists = Test-Path -LiteralPath $fullPath
    }
  }
  $results
}

