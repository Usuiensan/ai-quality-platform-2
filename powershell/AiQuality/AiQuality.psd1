@{
  RootModule = 'AiQuality.psm1'
  ModuleVersion = '0.4.0'
  GUID = '7f0ff1f2-d7b7-45b8-8d6e-f6a6f62946b3'
  Author = 'Usuiensan'
  CompanyName = 'Usuiensan'
  Copyright = '(c) Usuiensan. All rights reserved.'
  Description = 'AI品質管理プラットフォームをGitHubリポジトリへ導入するPowerShell 7モジュール'
  PowerShellVersion = '7.0'
  FunctionsToExport = @(
    'New-AiManagedRepo',
    'Enable-AiQuality',
    'Update-AiQuality',
    'Test-AiQuality',
    'Get-AiQualityStatus',
    'Set-AiQualityRuleset'
  )
  CmdletsToExport = @()
  VariablesToExport = '*'
  AliasesToExport = @()
}
