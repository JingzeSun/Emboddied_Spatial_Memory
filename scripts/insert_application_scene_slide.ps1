param(
    [string]$InputPath = "prototype/dynamic_spatial_revision_report_v1_0.pptx",
    [string]$ImagePath = "prototype/assets/world_model_application_scene_v1.png",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v1_1.pptx"
)

$ErrorActionPreference = "Stop"

function Rgb([int]$r, [int]$g, [int]$b) {
    return $r + 256 * $g + 65536 * $b
}

$C = @{
    Bg = Rgb 11 18 32
    Card = Rgb 20 33 56
    White = Rgb 245 247 250
    Muted = Rgb 159 176 197
    Blue = Rgb 79 140 255
    Cyan = Rgb 55 215 199
    Amber = Rgb 255 180 84
    Line = Rgb 58 78 108
}

$FontCN = "Microsoft YaHei"
$FontMono = "Consolas"
$SlideW = 960
$SlideH = 540

function Resolve-ProjectPath {
    param([string]$PathValue, [string]$ProjectRoot)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PathValue))
}

function Add-Shape {
    param(
        $Slide,
        [int]$Type,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [int]$Fill,
        [int]$Line,
        [double]$Transparency = 0
    )
    $shape = $Slide.Shapes.AddShape($Type, $X, $Y, $W, $H)
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $Fill
    $shape.Fill.Transparency = [Math]::Min(1.0, [Math]::Max(0.0, $Transparency / 100.0))
    $shape.Line.ForeColor.RGB = $Line
    $shape.Line.Weight = 1
    return $shape
}

function Add-Text {
    param(
        $Slide,
        [string]$Text,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [double]$Size,
        [int]$Color,
        [bool]$Bold = $false,
        [int]$Align = 1,
        [string]$Font = $FontCN,
        [int]$VAnchor = 1
    )
    $shape = $Slide.Shapes.AddTextbox(1, $X, $Y, $W, $H)
    $shape.Line.Visible = 0
    $shape.Fill.Visible = 0
    $tf = $shape.TextFrame2
    $tf.WordWrap = -1
    $tf.AutoSize = 0
    $tf.MarginLeft = 0
    $tf.MarginRight = 0
    $tf.MarginTop = 0
    $tf.MarginBottom = 0
    $tf.VerticalAnchor = $VAnchor
    $tf.TextRange.Text = $Text
    $tf.TextRange.Font.Name = $Font
    $tf.TextRange.Font.NameFarEast = $FontCN
    $tf.TextRange.Font.Size = $Size
    $tf.TextRange.Font.Bold = $(if ($Bold) { -1 } else { 0 })
    $tf.TextRange.Font.Fill.ForeColor.RGB = $Color
    $tf.TextRange.ParagraphFormat.Alignment = $Align
    $shape.Width = $W
    $shape.Height = $H
    return $shape
}

function Add-Line {
    param(
        $Slide,
        [double]$X1,
        [double]$Y1,
        [double]$X2,
        [double]$Y2,
        [int]$Color,
        [double]$Weight = 1
    )
    $line = $Slide.Shapes.AddLine($X1, $Y1, $X2, $Y2)
    $line.Line.ForeColor.RGB = $Color
    $line.Line.Weight = $Weight
    return $line
}

function Add-CalloutCard {
    param(
        $Slide,
        [double]$Y,
        [double]$H,
        [int]$Accent,
        [string]$Title,
        [string]$Body
    )
    [void](Add-Shape $Slide 5 638 $Y 276 $H $C.Card $C.Line)
    [void](Add-Shape $Slide 1 638 $Y 5 $H $Accent $Accent)
    [void](Add-Text $Slide $Title 656 ($Y + 13) 238 22 12.5 $Accent $true 1 $FontCN 1)
    [void](Add-Text $Slide $Body 656 ($Y + 40) 238 ($H - 49) 9.5 $C.White $false 1 $FontCN 1)
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$inputAbs = Resolve-ProjectPath $InputPath $projectRoot
$imageAbs = Resolve-ProjectPath $ImagePath $projectRoot
$outputAbs = Resolve-ProjectPath $OutputPath $projectRoot

if (-not (Test-Path -LiteralPath $inputAbs)) {
    throw "Input presentation does not exist: $inputAbs"
}
if (-not (Test-Path -LiteralPath $imageAbs)) {
    throw "Application-scene image does not exist: $imageAbs"
}
if (Test-Path -LiteralPath $outputAbs) {
    throw "Refusing to overwrite existing presentation: $outputAbs"
}

$ppt = New-Object -ComObject PowerPoint.Application
$presentation = $null
try {
    $presentation = $ppt.Presentations.Open($inputAbs, $false, $false, $false)
    if ($presentation.PageSetup.SlideWidth -ne $SlideW -or $presentation.PageSetup.SlideHeight -ne $SlideH) {
        throw ("Unexpected slide size. Expected " + $SlideW + "x" + $SlideH + ".")
    }

    $slide = $presentation.Slides.Add(2, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $C.Bg

    [void](Add-Shape $slide 1 0 0 10 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide "应用场景 · 连续走廊探索" 46 28 260 16 9 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide "机器人边走边扩充世界，并用新证据主动验证与局部修订" 46 49 868 42 25 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 46 97 914 97 $C.Line 1)
    [void](Add-Text $slide "02" 886 28 28 18 9 $C.Muted $true 2 $FontMono 1)

    [void](Add-Shape $slide 5 44 119 574 326 $C.Card $C.Line)
    $picture = $slide.Shapes.AddPicture($imageAbs, 0, -1, 46, 121, 570, 321)
    $picture.Line.Visible = 0

    Add-CalloutCard $slide 119 94 $C.Blue "边走边扩充" "重复走廊先形成候选结构；未见区域不直接写成世界事实。"
    Add-CalloutCard $slide 221 94 $C.Cyan "主动取证确认" "转角视图与深度用于判断左转、回环，还是定位仍不确定。"
    Add-CalloutCard $slide 323 122 $C.Amber "有限、可追溯修订" "椅子搬走只修改受影响关系；人物身份和两个木箱实例继续保留。"

    [void](Add-Line $slide 46 473 914 473 $C.Line 0.8)
    [void](Add-Text $slide "青蓝实线＝已确认世界    橙色虚线＝预测候选    视锥＝主动获得的新证据" 46 485 868 18 8.5 $C.Muted $false 1 $FontCN 1)
    [void](Add-Text $slide "场景目的：让世界模型在持续移动中同时处理结构扩充、歧义消解与局部版本修订。" 46 511 868 13 7.4 $C.Muted $false 1 $FontCN 1)

    for ($slideIndex = 2; $slideIndex -le $presentation.Slides.Count; $slideIndex++) {
        $numberText = "{0:D2}" -f $slideIndex
        foreach ($shape in @($presentation.Slides.Item($slideIndex).Shapes)) {
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
                $text = $shape.TextFrame.TextRange.Text.Trim()
                if ($text -match "^\d{2}$" -and $shape.Left -gt 820 -and $shape.Top -lt 60) {
                    $shape.TextFrame.TextRange.Text = $numberText
                }
            }
        }
    }

    foreach ($shape in @($presentation.Slides.Item(1).Shapes)) {
        if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
            $text = $shape.TextFrame.TextRange.Text
            if ($text -like "*v1.0*") {
                $shape.TextFrame.TextRange.Text = $text.Replace("v1.0", "v1.1")
            }
        }
    }

    $presentation.SaveAs($outputAbs, 24)
    $presentation.Close()
    $presentation = $null
}
finally {
    if ($null -ne $presentation) {
        $presentation.Close()
    }
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ppt) | Out-Null
}

Write-Output $outputAbs
