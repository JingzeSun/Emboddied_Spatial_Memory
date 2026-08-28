param(
    [string]$ContentPath = "scripts/dynamic_memory_prior_work_ppt_content.json",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v0_2.pptx"
)

$ErrorActionPreference = "Stop"
$builderPath = Join-Path $PSScriptRoot "build_dynamic_memory_prior_work_ppt.ps1"
$code = [System.IO.File]::ReadAllText($builderPath, [System.Text.Encoding]::UTF8)
$escapedRoot = $PSScriptRoot.Replace("'", "''")
$code = $code.Replace('$PSScriptRoot', "'$escapedRoot'")
$scriptBlock = [ScriptBlock]::Create($code)
& $scriptBlock -ContentPath $ContentPath -OutputPath $OutputPath
