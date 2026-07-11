function Assert-AiQualityPowerShell {
  if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7以上で実行してください。'
  }
}

function Assert-GhCli {
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if (-not $gh) {
    throw 'GitHub CLI gh が見つかりません。インストール後に gh auth login を実行してください。'
  }
}

function Invoke-GhJson {
  param(
    [Parameter(Mandatory)][string[]]$Arguments
  )
  Assert-GhCli
  $output = & gh @Arguments 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "gh コマンドに失敗しました: gh $($Arguments -join ' ')`n$output"
  }
  if ([string]::IsNullOrWhiteSpace($output)) {
    return $null
  }
  return $output | ConvertFrom-Json
}

function Invoke-Gh {
  param(
    [Parameter(Mandatory)][string[]]$Arguments,
    [switch]$DryRun
  )
  Assert-GhCli
  if ($DryRun) {
    Write-Information "DRY-RUN: gh $($Arguments -join ' ')" -InformationAction Continue
    return $null
  }
  $output = & gh @Arguments 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "gh コマンドに失敗しました: gh $($Arguments -join ' ')`n$output"
  }
  return $output
}

function New-AiQualityConfigText {
  param(
    [Parameter(Mandatory)][string]$Preset,
    [string]$WorkflowRef = $script:DefaultWorkflowRef
  )
  @"
version: 1

preset: $($Preset.ToLowerInvariant())
risk_level: medium

reviewers:
  architecture: false
  requirements: true
  code: true
  security: true
  tests: true
  documentation: true
  final_audit: true

autofix:
  enabled: true
  max_rounds: 3
  max_changed_lines_per_round: 300
  max_total_changed_lines: 800
  allow_dependency_changes: false
  allow_workflow_changes: false

human_gate:
  dependency_changes: true
  workflow_changes: true
  authentication_changes: true
  authorization_changes: true
  deployment_changes: true
  secret_handling_changes: true
  destructive_operations: true

localization:
  human_language: ja
  commit_language: ja
  pull_request_language: ja
  review_language: ja
  documentation_language: ja
  machine_identifiers: en

platform:
  repository: $script:DefaultPlatformRepository
  workflow_ref: $WorkflowRef
"@
}

function New-AiQualityWorkflowText {
  param(
    [string]$PlatformRepository = $script:DefaultPlatformRepository,
    [string]$WorkflowRef = $script:DefaultWorkflowRef
  )
  @"
name: AI Quality Gate

on:
  pull_request:
    branches:
      - main
    types:
      - opened
      - synchronize
      - reopened
      - ready_for_review

permissions:
  contents: read
  pull-requests: write
  checks: write

concurrency:
  group: ai-quality-`${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  quality:
    name: AI品質ゲート
    uses: $PlatformRepository/.github/workflows/reusable-quality-gate.yml@$WorkflowRef
    secrets: inherit
"@
}

function New-AiQualityPullRequestTemplateText {
  @"
## 概要

このPRで変更する内容を簡潔に記載してください。

## 変更理由

なぜこの変更が必要かを記載してください。

## 動作確認

- [ ] 単体テスト
- [ ] 静的解析
- [ ] 型検査
- [ ] 実環境確認

## 影響範囲

影響する機能、設定、運用手順を記載してください。

## リスク

残存リスクまたは破壊的変更の有無を記載してください。

## 未確認事項

現時点で把握している未確認事項を記載してください。

## 最終判定

- [ ] 残存リスクを確認した
- [ ] マージしてよい
"@
}

function Set-AiQualityFiles {
  param(
    [Parameter(Mandatory)][string]$RepositoryPath,
    [string]$Preset = 'Generic',
    [string]$PlatformRepository = $script:DefaultPlatformRepository,
    [string]$WorkflowRef = $script:DefaultWorkflowRef,
    [switch]$Force
  )
  $root = Resolve-Path -LiteralPath $RepositoryPath
  $workflowDir = Join-Path $root '.github/workflows'
  $templateDir = Join-Path $root '.github'
  New-Item -ItemType Directory -Force -Path $workflowDir | Out-Null
  New-Item -ItemType Directory -Force -Path $templateDir | Out-Null

  $targets = @(
    @{ Path = Join-Path $workflowDir 'ai-quality.yml'; Text = New-AiQualityWorkflowText -PlatformRepository $PlatformRepository -WorkflowRef $WorkflowRef },
    @{ Path = Join-Path $root '.ai-quality.yml'; Text = New-AiQualityConfigText -Preset $Preset -WorkflowRef $WorkflowRef },
    @{ Path = Join-Path $templateDir 'pull_request_template.md'; Text = New-AiQualityPullRequestTemplateText }
  )

  foreach ($target in $targets) {
    if ((Test-Path -LiteralPath $target.Path) -and -not $Force) {
      continue
    }
    Set-Content -LiteralPath $target.Path -Value $target.Text -Encoding utf8NoBOM
  }
}

function Get-AiQualityWorkflowRef {
  param([Parameter(Mandatory)][string]$Content)
  if ($Content -match 'ai-quality-platform/.github/workflows/reusable-quality-gate.yml@([^\s]+)') {
    return $Matches[1]
  }
  return $null
}

function Get-RepositoryDefaultBranch {
  param(
    [Parameter(Mandatory)][string]$Owner,
    [Parameter(Mandatory)][string]$Name
  )
  $repo = Invoke-GhJson -Arguments @('repo', 'view', "$Owner/$Name", '--json', 'defaultBranchRef')
  return $repo.defaultBranchRef.name
}

