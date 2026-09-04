param(
    [string]$InputPath = "prototype/dynamic_spatial_revision_report_v1_1.pptx",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v1_2.pptx"
)

$ErrorActionPreference = "Stop"

function Rgb([int]$r, [int]$g, [int]$b) {
    return $r + 256 * $g + 65536 * $b
}

$C = @{
    Bg = Rgb 11 18 32
    Card = Rgb 20 33 56
    Card2 = Rgb 25 42 70
    White = Rgb 245 247 250
    Muted = Rgb 159 176 197
    Blue = Rgb 79 140 255
    Cyan = Rgb 55 215 199
    Amber = Rgb 255 180 84
    Red = Rgb 255 107 122
    Green = Rgb 99 215 151
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
        [double]$Weight = 1,
        [bool]$Arrow = $false
    )
    $line = $Slide.Shapes.AddLine($X1, $Y1, $X2, $Y2)
    $line.Line.ForeColor.RGB = $Color
    $line.Line.Weight = $Weight
    if ($Arrow) {
        $line.Line.EndArrowheadStyle = 3
    }
    return $line
}

function Add-Pill {
    param(
        $Slide,
        [string]$Text,
        [double]$X,
        [double]$Y,
        [double]$W,
        [int]$Fill,
        [int]$Color
    )
    [void](Add-Shape $Slide 5 $X $Y $W 25 $Fill $Fill)
    [void](Add-Text $Slide $Text ($X + 6) ($Y + 1) ($W - 12) 22 9 $Color $true 2 $FontCN 3)
}

function Add-FactRow {
    param(
        $Slide,
        [string]$Label,
        [string]$Value,
        [double]$X,
        [double]$Y,
        [double]$W,
        [int]$Accent
    )
    [void](Add-Shape $Slide 1 $X $Y 4 32 $Accent $Accent)
    [void](Add-Text $Slide $Label ($X + 11) ($Y + 2) 68 14 8.5 $Accent $true 1 $FontCN 1)
    [void](Add-Text $Slide $Value ($X + 11) ($Y + 15) ($W - 18) 16 9.2 $C.White $false 1 $FontCN 1)
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$inputAbs = Resolve-ProjectPath $InputPath $projectRoot
$outputAbs = Resolve-ProjectPath $OutputPath $projectRoot

if (-not (Test-Path -LiteralPath $inputAbs)) {
    throw "Input presentation does not exist: $inputAbs"
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
    if ($presentation.Slides.Count -lt 2) {
        throw "Presentation has no slide 2."
    }

    $presentation.Slides.Item(2).Delete()
    $slide = $presentation.Slides.Add(2, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $C.Bg

    [void](Add-Shape $slide 1 0 0 10 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide "核心贡献 · 单一母命题" 46 28 260 16 9 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide "新证据如何有限、可追溯地重组旧世界信念" 46 49 868 42 25 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 46 97 914 97 $C.Line 1 $false)
    [void](Add-Text $slide "02" 886 28 28 18 9 $C.Muted $true 2 $FontMono 1)

    Add-Pill $slide "前置：预测 / 区域绑定" 46 108 204 $C.Card2 $C.Blue
    [void](Add-Line $slide 256 120 354 120 $C.Line 1.4 $true)
    Add-Pill $slide "核心：有界 posterior revision" 362 108 238 $C.Card2 $C.Amber
    [void](Add-Line $slide 608 120 703 120 $C.Line 1.4 $true)
    Add-Pill $slide "下游：主动补证 / Top-K" 711 108 203 $C.Card2 $C.Cyan

    # Left: old belief and evidence.
    [void](Add-Shape $slide 5 46 148 206 116 $C.Card $C.Line)
    [void](Add-Text $slide "旧世界信念  B_t" 60 160 178 18 12 $C.Blue $true 1 $FontCN 1)
    [void](Add-Text $slide "chair@A：当前有效" 60 187 178 16 9.5 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "cart ─supports→ box" 60 209 178 16 9.5 $C.White $false 1 $FontMono 1)
    [void](Add-Text $slide "plant@P：无关事实" 60 231 178 16 9.5 $C.Green $false 1 $FontCN 1)

    [void](Add-Shape $slide 5 46 278 206 132 $C.Card $C.Line)
    [void](Add-Text $slide "新证据  O_{t+1}" 60 290 178 18 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide "B 处可靠看到同一把椅子" 60 317 178 18 9.4 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "A 清晰可见且为空" 60 342 178 16 9.4 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "pose / visibility / identity 可信" 60 365 178 20 8.8 $C.Muted $false 1 $FontCN 1)
    [void](Add-Text $slide "区域已绑定到 chair_1" 60 388 178 16 9.2 $C.Cyan $false 1 $FontCN 1)

    [void](Add-Line $slide 258 206 286 206 $C.Blue 1.8 $true)
    [void](Add-Line $slide 258 344 286 344 $C.Cyan 1.8 $true)

    # Center: the actual contribution.
    [void](Add-Shape $slide 5 288 148 374 262 $C.Card $C.Amber)
    [void](Add-Text $slide "Evidence-Gated Affected-Subgraph Revision" 305 160 340 22 12 $C.Amber $true 2 $FontMono 1)
    [void](Add-Text $slide "不是把新帧平均进去，而是生成一条可审计的后验修改记录" 305 187 340 18 9.3 $C.White $false 2 $FontCN 1)

    Add-FactRow $slide "① 证据路径" "REVISE：不是 reveal / occlusion / noise" 306 218 338 $C.Cyan
    Add-FactRow $slide "② Typed edit" "旧位置失效 + 新位置 RELINK；identity 保持" 306 257 338 $C.Amber
    Add-FactRow $slide "③ 修改范围" "affected={chair location}；control={plant, actor type}" 306 296 338 $C.Blue
    Add-FactRow $slide "④ 传播与停止" "只沿许可依赖传播；无依赖边前 STOP" 306 335 338 $C.Green
    Add-FactRow $slide "⑤ 版本提交" "原子 apply；保存 valid time、旧版本与证据来源" 306 374 338 $C.Red

    [void](Add-Line $slide 668 279 696 279 $C.Amber 2 $true)

    # Right: posterior along the three axes.
    [void](Add-Shape $slide 5 698 148 216 262 $C.Card $C.Cyan)
    [void](Add-Text $slide "后验世界信念  B_{t+1}" 712 160 188 20 12 $C.Cyan $true 2 $FontCN 1)
    Add-FactRow $slide "语义状态" "A 位置 invalid；B 位置 confirmed" 714 198 184 $C.Cyan
    Add-FactRow $slide "拓扑关系" "chair：A → B；必要依赖同步" 714 240 184 $C.Amber
    Add-FactRow $slide "有效时间" "A.valid_to=t；B.valid_from=t+1" 714 282 184 $C.Red
    Add-FactRow $slide "无关保持" "plant、人物类型、其它区域不变" 714 324 184 $C.Green
    Add-FactRow $slide "可追溯" "新旧版本均回到动作与观测" 714 366 184 $C.Blue

    # Bottom: what the paper actually measures.
    [void](Add-Shape $slide 5 46 431 868 58 $C.Card2 $C.Line)
    [void](Add-Text $slide "论文核心判据" 63 443 105 18 10.5 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide "必要修改是否完整  ↑" 176 443 164 18 10 $C.White $true 2 $FontCN 1)
    [void](Add-Text $slide "无关事实是否保持  ↑" 344 443 164 18 10 $C.Green $true 2 $FontCN 1)
    [void](Add-Text $slide "越界修改是否减少  ↓" 512 443 164 18 10 $C.Red $true 2 $FontCN 1)
    [void](Add-Text $slide "版本与停止是否正确  ↑" 680 443 214 18 10 $C.Cyan $true 2 $FontCN 1)
    [void](Add-Text $slide "同一感知、预测和 association 输入下，只比较 revision controller；不能用更强前端或任务总分冒充修订贡献。" 63 468 831 14 8.3 $C.Muted $false 2 $FontCN 1)

    [void](Add-Line $slide 46 509 914 509 $C.Line 0.8 $false)
    [void](Add-Text $slide "房间布局负责识别当前结构，Top-K 负责读取优先级，动作预测负责预期先验；本项目核心只回答旧世界应该怎样改变。" 46 515 868 13 7.5 $C.Muted $false 1 $FontCN 1)

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
            if ($text -like "*v1.1*") {
                $shape.TextFrame.TextRange.Text = $text.Replace("v1.1", "v1.2")
            }
            if ($shape.TextFrame.TextRange.Text -like "*2026-08-28*") {
                $shape.TextFrame.TextRange.Text = $shape.TextFrame.TextRange.Text.Replace("2026-08-28", "2026-08-29")
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
