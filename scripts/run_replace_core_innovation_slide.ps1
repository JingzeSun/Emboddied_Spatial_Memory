param(
    [string]$InputPath = "prototype/dynamic_spatial_revision_report_v1_1.pptx",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v1_2.pptx"
)

$ErrorActionPreference = "Stop"
$builderPath = Join-Path $PSScriptRoot "replace_core_innovation_slide.ps1"
$code = [System.IO.File]::ReadAllText($builderPath, [System.Text.Encoding]::UTF8)
$escapedRoot = $PSScriptRoot.Replace("'", "''")
$code = $code.Replace('$PSScriptRoot', "'$escapedRoot'")
$scriptBlock = [ScriptBlock]::Create($code)
& $scriptBlock -InputPath $InputPath -OutputPath $OutputPath
