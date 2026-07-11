$script:ModuleRoot = $PSScriptRoot
$script:DefaultPlatformRepository = 'Usuiensan/ai-quality-platform'
$script:DefaultTemplateRepository = 'Usuiensan/repository-template'
$script:DefaultWorkflowRef = 'v1'

Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'Private') -Filter '*.ps1' -ErrorAction SilentlyContinue |
  ForEach-Object { . $_.FullName }

Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'Public') -Filter '*.ps1' -ErrorAction SilentlyContinue |
  ForEach-Object { . $_.FullName }

Export-ModuleMember -Function @(
  'New-AiManagedRepo',
  'Enable-AiQuality',
  'Update-AiQuality',
  'Test-AiQuality',
  'Get-AiQualityStatus',
  'Set-AiQualityRuleset'
)
