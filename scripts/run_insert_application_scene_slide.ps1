param(
    [string]$InputPath = "prototype/dynamic_spatial_revision_report_v1_0.pptx",
    [string]$ImagePath = "prototype/assets/world_model_application_scene_v1.png",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v1_1.pptx"
)

$ErrorActionPreference = "Stop"
$builderPath = Join-Path $PSScriptRoot "insert_application_scene_slide.ps1"
$code = [System.IO.File]::ReadAllText($builderPath, [System.Text.Encoding]::UTF8)
$escapedRoot = $PSScriptRoot.Replace("'", "''")
$code = $code.Replace('$PSScriptRoot', "'$escapedRoot'")
$scriptBlock = [ScriptBlock]::Create($code)
& $scriptBlock -InputPath $InputPath -ImagePath $ImagePath -OutputPath $OutputPath
