param(
    [string]$ContentPath = "scripts/dynamic_memory_prior_work_ppt_content.json",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v0_3.pptx"
)

$ErrorActionPreference = "Stop"

function Rgb([int]$r, [int]$g, [int]$b) {
    return $r + 256 * $g + 65536 * $b
}

$C = @{
    Bg = Rgb 11 18 32
    Bg2 = Rgb 16 27 47
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
        [double]$Size = 16,
        [int]$Color = $C.White,
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
        [int]$Color = $C.Line,
        [double]$Weight = 1.5,
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

function Add-CircleLabel {
    param(
        $Slide,
        [string]$Text,
        [double]$X,
        [double]$Y,
        [double]$D,
        [int]$Fill = $C.Blue,
        [double]$Size = 12
    )
    [void](Add-Shape $Slide 9 $X $Y $D $D $Fill $Fill)
    [void](Add-Text $Slide $Text $X $Y $D $D $Size $C.White $true 2 $FontCN 3)
}

function Add-Pill {
    param(
        $Slide,
        [string]$Text,
        [double]$X,
        [double]$Y,
        [double]$W,
        [int]$Fill = $C.Card2,
        [int]$Color = $C.Cyan,
        [double]$Size = 10
    )
    [void](Add-Shape $Slide 5 $X $Y $W 25 $Fill $Fill)
    [void](Add-Text $Slide $Text ($X + 7) ($Y + 1) ($W - 14) 23 $Size $Color $true 2 $FontCN 3)
}

function Add-SlideBase {
    param(
        $Presentation,
        [int]$Index,
        [string]$Title,
        [string]$Section
    )
    $slide = $Presentation.Slides.Add($Index, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $C.Bg
    [void](Add-Shape $slide 1 0 0 10 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide $Section 46 28 220 16 9 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $Title 46 49 868 42 25 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 46 97 914 97 $C.Line 1 $false)
    [void](Add-Text $slide ("{0:D2}" -f $Index) 886 28 28 18 9 $C.Muted $true 2 $FontMono 1)
    return $slide
}

function Add-Footer {
    param($Slide, [string]$Text)
    [void](Add-Line $Slide 46 509 914 509 $C.Line 0.8 $false)
    [void](Add-Text $Slide $Text 46 515 868 13 7.4 $C.Muted $false 1 $FontCN 1)
}

function Add-Bullets {
    param(
        $Slide,
        $Items,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$Gap = 42,
        [double]$Size = 12,
        [int]$BulletColor = $C.Cyan,
        [int]$TextColor = $C.White
    )
    $i = 0
    foreach ($item in $Items) {
        $yy = $Y + $i * $Gap
        [void](Add-Shape $Slide 9 $X ($yy + 6) 8 8 $BulletColor $BulletColor)
        [void](Add-Text $Slide ([string]$item) ($X + 18) $yy ($W - 18) ($Gap - 2) $Size $TextColor $false 1 $FontCN 1)
        $i++
    }
}

function Add-Node {
    param(
        $Slide,
        [string]$Text,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [int]$Accent = $C.Blue,
        [double]$Size = 12
    )
    [void](Add-Shape $Slide 5 $X $Y $W $H $C.Card2 $Accent)
    [void](Add-Shape $Slide 1 $X $Y 5 $H $Accent $Accent)
    [void](Add-Text $Slide $Text ($X + 12) ($Y + 3) ($W - 18) ($H - 6) $Size $C.White $true 2 $FontCN 3)
}

function Add-PaperCards {
    param($Presentation, [int]$Index, $Data)
    $slide = Add-SlideBase $Presentation $Index $Data.title "同行评审文献基础"
    $xs = @(46, 340, 634)
    $accents = @($C.Blue, $C.Cyan, $C.Amber)
    for ($i = 0; $i -lt 3; $i++) {
        $item = $Data.items[$i]
        $x = $xs[$i]
        [void](Add-Shape $slide 5 $x 122 280 365 $C.Card $C.Line)
        [void](Add-Shape $slide 1 $x 122 6 365 $accents[$i] $accents[$i])
        [void](Add-Text $slide $item.paper ($x + 18) 139 244 31 15 $C.White $true 1 $FontCN 1)
        Add-Pill $slide $item.venue ($x + 18) 174 175 $accents[$i] $C.White 9
        [void](Add-Text $slide "方法" ($x + 18) 216 52 18 10.5 $accents[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $item.method ($x + 18) 239 248 63 10.2 $C.White $false 1 $FontCN 1)
        [void](Add-Line $slide ($x + 18) 309 ($x + 262) 309 $C.Line 0.7 $false)
        [void](Add-Text $slide "借鉴" ($x + 18) 322 52 18 10.5 $C.Green $true 1 $FontCN 1)
        [void](Add-Text $slide $item.borrow ($x + 18) 345 244 53 10.1 $C.White $false 1 $FontCN 1)
        [void](Add-Line $slide ($x + 18) 405 ($x + 262) 405 $C.Line 0.7 $false)
        [void](Add-Text $slide "不足" ($x + 18) 418 52 18 10.5 $C.Red $true 1 $FontCN 1)
        [void](Add-Text $slide $item.gap ($x + 18) 441 244 38 9.6 $C.Muted $false 1 $FontCN 1)
    }
    Add-Footer $slide $Data.source
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contentAbs = if ([System.IO.Path]::IsPathRooted($ContentPath)) {
    $ContentPath
}
else {
    Join-Path $root $ContentPath
}
$outputAbs = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
}
else {
    Join-Path $root $OutputPath
}
$data = ConvertFrom-Json (Get-Content -Raw -Encoding UTF8 -LiteralPath $contentAbs)

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = -1
$presentation = $null
try {
    $presentation = $ppt.Presentations.Add()
    $presentation.PageSetup.SlideWidth = $SlideW
    $presentation.PageSetup.SlideHeight = $SlideH

    # 01 Cover
    $slide = $presentation.Slides.Add(1, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $C.Bg
    [void](Add-Shape $slide 9 670 -120 410 410 $C.Blue $C.Blue 84)
    [void](Add-Shape $slide 9 750 220 285 285 $C.Cyan $C.Cyan 90)
    [void](Add-Shape $slide 1 0 0 12 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide "研究设想 · 文献边界 · 方法蓝图" 62 68 400 24 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.title 62 112 735 112 33 $C.White $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.subtitle 64 240 680 58 16 $C.Muted $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 62 329 596 72 $C.Card $C.Line)
    [void](Add-Text $slide "本版范围" 80 344 80 20 11 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide "只完成文献基础与概念架构；场景和训练在概念冻结后另行设计。" 169 340 463 42 13.5 $C.White $true 1 $FontCN 3)
    $tags = @("Peer-reviewed foundations", "Controlled write path", "Method WBS", "Experiment coverage")
    $tagX = 62
    foreach ($tag in $tags) {
        Add-Pill $slide $tag $tagX 435 174 $C.Card2 $C.Cyan 9
        $tagX += 184
    }
    [void](Add-Text $slide ($data.meta.date + "  ·  " + $data.meta.author) 62 496 520 18 9 $C.Muted $false 1 $FontCN 1)

    # 02 Framing
    $d = $data.slides.framing
    $slide = Add-SlideBase $presentation 2 $d.title "汇报边界"
    $boxXs = @(46, 490)
    $colors = @($C.Blue, $C.Cyan)
    for ($i = 0; $i -lt 2; $i++) {
        $item = $d.questions[$i]
        $x = $boxXs[$i]
        [void](Add-Shape $slide 5 $x 126 424 226 $C.Card $C.Line)
        Add-Pill $slide $item.label ($x + 22) 145 126 $colors[$i] $C.White 10
        [void](Add-Text $slide $item.question ($x + 22) 190 376 46 16 $C.White $true 1 $FontCN 1)
        [void](Add-Line $slide ($x + 22) 247 ($x + 402) 247 $C.Line 0.8 $false)
        [void](Add-Text $slide $item.answer ($x + 22) 268 376 63 12 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 371 868 58 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.boundary 66 382 828 36 12.2 $C.Amber $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 444 868 47 $C.Card2 $C.Green)
    [void](Add-Text $slide $d.status 66 454 828 28 12.5 $C.Green $true 2 $FontCN 3)
    Add-Footer $slide "本版刻意停止在场景之前，避免先写故事、后补定义。"

    # 03 Timeline
    $d = $data.slides.timeline
    $slide = Add-SlideBase $presentation 3 $d.title "能力演进"
    [void](Add-Line $slide 88 282 872 282 $C.Line 3 $false)
    $positions = @(92, 244, 396, 548, 700, 852)
    for ($i = 0; $i -lt 6; $i++) {
        $ev = $d.events[$i]
        $x = $positions[$i]
        $top = ($i % 2 -eq 0)
        Add-CircleLabel $slide "" ($x - 9) 273 18 $C.Cyan 1
        if ($top) {
            [void](Add-Line $slide $x 273 $x 218 $C.Line 1.5 $false)
            [void](Add-Text $slide $ev.year ($x - 45) 120 90 20 11 $C.Amber $true 2 $FontMono 1)
            [void](Add-Text $slide $ev.paper ($x - 65) 147 130 28 12.2 $C.White $true 2 $FontCN 1)
            [void](Add-Text $slide $ev.claim ($x - 65) 179 130 42 10.2 $C.Muted $false 2 $FontCN 1)
        }
        else {
            [void](Add-Line $slide $x 291 $x 342 $C.Line 1.5 $false)
            [void](Add-Text $slide $ev.year ($x - 45) 354 90 20 11 $C.Amber $true 2 $FontMono 1)
            [void](Add-Text $slide $ev.paper ($x - 66) 380 132 28 12.2 $C.White $true 2 $FontCN 1)
            [void](Add-Text $slide $ev.claim ($x - 66) 412 132 42 10.2 $C.Muted $false 2 $FontCN 1)
        }
    }
    Add-Footer $slide $d.source

    # 04-05 Peer-reviewed foundations
    Add-PaperCards $presentation 4 $data.slides.foundations_a
    Add-PaperCards $presentation 5 $data.slides.foundations_b

    # 06 Preprints
    $d = $data.slides.preprints
    $slide = Add-SlideBase $presentation 6 $d.title "创新性查重"
    [void](Add-Shape $slide 5 46 122 550 362 $C.Card $C.Line)
    [void](Add-Text $slide "FARM" 68 140 100 29 18 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.paper 68 174 504 28 10.8 $C.White $true 1 $FontCN 1)
    Add-Pill $slide "PREPRINT ONLY" 68 208 132 $C.Red $C.White 9
    [void](Add-Text $slide $d.farm.status 211 210 359 23 9.2 $C.Muted $false 1 $FontCN 1)
    [void](Add-Text $slide "它已经覆盖" 68 252 92 20 10.5 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.covered 168 249 402 49 10.5 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "我们的差异" 68 316 92 20 10.5 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.difference 168 313 402 64 10.5 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "如何使用" 68 397 92 20 10.5 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.use 168 394 402 55 10.3 $C.White $false 1 $FontCN 1)

    [void](Add-Shape $slide 5 616 122 298 362 $C.Bg2 $C.Line)
    [void](Add-Text $slide "其它 novelty watch" 638 141 250 24 13 $C.Amber $true 1 $FontCN 1)
    Add-Bullets $slide $d.watch 638 180 252 48 10.2 $C.Amber $C.White
    [void](Add-Shape $slide 5 632 416 266 52 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.risk 645 424 240 36 9.6 $C.Red $true 1 $FontCN 3)
    Add-Footer $slide "预印本可以改变我们的 novelty claim 和基线设计，但不能替代已评审文献的事实证据。"

    # 07 Matrix
    $d = $data.slides.matrix
    $slide = Add-SlideBase $presentation 7 $d.title "横向比较"
    $x0 = 36
    $y0 = 122
    $tableW = 888
    $rowNameW = 148
    $colW = ($tableW - $rowNameW) / 8
    $headerH = 58
    $rowH = 34
    [void](Add-Shape $slide 5 $x0 $y0 $tableW 333 $C.Card $C.Line)
    [void](Add-Text $slide "工作" ($x0 + 10) ($y0 + 17) ($rowNameW - 20) 24 10.5 $C.Muted $true 1 $FontCN 3)
    for ($j = 0; $j -lt $d.columns.Count; $j++) {
        $cx = $x0 + $rowNameW + $j * $colW
        [void](Add-Line $slide $cx $y0 $cx ($y0 + 330) $C.Line 0.6 $false)
        [void](Add-Text $slide $d.columns[$j] ($cx + 3) ($y0 + 7) ($colW - 6) 44 8.4 $C.Muted $true 2 $FontCN 3)
    }
    [void](Add-Line $slide $x0 ($y0 + $headerH) ($x0 + $tableW) ($y0 + $headerH) $C.Line 1 $false)
    for ($i = 0; $i -lt $d.rows.Count; $i++) {
        $row = $d.rows[$i]
        $ry = $y0 + $headerH + $i * $rowH
        if ($i % 2 -eq 1) {
            [void](Add-Shape $slide 1 ($x0 + 1) $ry ($tableW - 2) $rowH $C.Bg2 $C.Bg2)
        }
        [void](Add-Text $slide $row.paper ($x0 + 10) ($ry + 6) ($rowNameW - 16) 25 9.2 $C.White $true 1 $FontCN 3)
        for ($j = 0; $j -lt $row.values.Count; $j++) {
            $value = [string]$row.values[$j]
            $color = if ($value -eq "✓") {
                $C.Cyan
            }
            elseif ($value -eq "△") {
                $C.Amber
            }
            elseif ($value -eq "目标") {
                $C.Green
            }
            else {
                $C.Muted
            }
            $cx = $x0 + $rowNameW + $j * $colW
            $size = if ($value.Length -gt 5) { 8.2 } elseif ($value.Length -gt 2) { 9.2 } else { 14 }
            [void](Add-Text $slide $value $cx ($ry + 5) $colW 25 $size $color $true 2 $FontCN 3)
        }
        [void](Add-Line $slide $x0 ($ry + $rowH) ($x0 + $tableW) ($ry + $rowH) $C.Line 0.4 $false)
    }
    [void](Add-Text $slide $d.note 46 462 868 31 8.8 $C.Muted $false 1 $FontCN 1)
    Add-Footer $slide "正式基石与预印本分级呈现；Current proposal 的绿色“目标”不是实验结果。"

    # 08 Gap synthesis
    $d = $data.slides.gap
    $slide = Add-SlideBase $presentation 8 $d.title "问题收敛"
    $routeXs = @(46, 264, 482, 700)
    $routeColors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green)
    for ($i = 0; $i -lt $d.routes.Count; $i++) {
        $route = $d.routes[$i]
        $x = $routeXs[$i]
        [void](Add-Shape $slide 5 $x 125 200 126 $C.Card $C.Line)
        [void](Add-Text $slide $route.name ($x + 16) 142 168 24 13 $routeColors[$i] $true 2 $FontCN 1)
        [void](Add-Text $slide $route.plain ($x + 16) 177 168 28 11.2 $C.White $true 2 $FontCN 1)
        [void](Add-Text $slide $route.papers ($x + 16) 215 168 22 9.6 $C.Muted $false 2 $FontCN 1)
    }
    [void](Add-Text $slide "缺失的受控 write path" 46 275 868 24 13 $C.Cyan $true 2 $FontCN 1)
    $flowX = 46
    foreach ($step in $d.write_path) {
        Add-Node $slide $step $flowX 314 132 48 $C.Cyan 10.4
        if ($flowX -lt 720) {
            [void](Add-Line $slide ($flowX + 134) 338 ($flowX + 143) 338 $C.Cyan 1.6 $true)
        }
        $flowX += 145
    }
    [void](Add-Shape $slide 5 46 386 868 72 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.claim 66 397 828 49 11.4 $C.White $true 2 $FontCN 3)
    [void](Add-Text $slide $d.not_claim 46 468 868 23 10.2 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "创新不是组件清单，而是可证伪的受控写入机制。"

    # 09 Full pipeline
    $d = $data.slides.pipeline
    $slide = Add-SlideBase $presentation 9 $d.title "核心方法"
    $inputXs = @(260, 407, 554)
    for ($i = 0; $i -lt $d.inputs.Count; $i++) {
        Add-Pill $slide $d.inputs[$i] $inputXs[$i] 113 132 $C.Card2 $C.Blue 9.5
    }
    [void](Add-Line $slide 480 141 480 160 $C.Line 1.8 $true)
    Add-Node $slide $d.observation 123 166 292 56 $C.Blue 10.6
    [void](Add-Text $slide "+" 461 176 38 35 22 $C.Amber $true 2 $FontCN 3)
    Add-Node $slide $d.expected 545 166 292 56 $C.Cyan 10.2
    [void](Add-Line $slide 269 224 424 249 $C.Line 1.6 $true)
    [void](Add-Line $slide 691 224 536 249 $C.Line 1.6 $true)
    Add-Node $slide $d.innovation 318 247 324 54 $C.Amber 11
    [void](Add-Line $slide 480 302 480 321 $C.Line 1.8 $true)
    $scopeXs = @(180, 390, 600)
    for ($i = 0; $i -lt $d.scope.Count; $i++) {
        Add-Node $slide $d.scope[$i] $scopeXs[$i] 326 180 44 $C.Cyan 9.8
        if ($i -lt 2) {
            [void](Add-Line $slide ($scopeXs[$i] + 181) 348 ($scopeXs[$i + 1] - 6) 348 $C.Cyan 1.5 $true)
        }
    }
    [void](Add-Line $slide 480 372 190 390 $C.Line 1.8 $true)
    Add-Node $slide $d.delta 46 393 288 58 $C.Blue 9.7
    [void](Add-Line $slide 336 422 366 422 $C.Line 1.6 $true)
    Add-Node $slide $d.executor 370 393 205 58 $C.Amber 10.2
    [void](Add-Line $slide 577 422 607 422 $C.Line 1.6 $true)
    Add-Node $slide $d.new_belief 611 393 303 58 $C.Green 10.3
    [void](Add-Shape $slide 5 46 464 424 31 $C.Card $C.Line)
    [void](Add-Text $slide $d.read 58 469 400 21 8.6 $C.Cyan $false 1 $FontCN 3)
    [void](Add-Shape $slide 5 490 464 424 31 $C.Card $C.Line)
    [void](Add-Text $slide $d.persist 502 469 400 21 8.6 $C.Green $false 1 $FontCN 3)
    Add-Footer $slide "核心保护：未经 typed executor 的输出不能直接改 SceneBelief。"

    # 10 Routing
    $d = $data.slides.routing
    $slide = Add-SlideBase $presentation 10 $d.title "差异判型"
    [void](Add-Shape $slide 5 46 113 868 38 $C.Card2 $C.Line)
    [void](Add-Text $slide ("证据类别：  " + ($d.evidence -join "   ·   ")) 60 121 840 22 9.6 $C.Muted $true 2 $FontCN 3)
    $modeXs = @(46, 340, 634)
    $modeYs = @(166, 298)
    $modeColors = @($C.Blue, $C.Green, $C.Red, $C.Cyan, $C.Amber, $C.Muted)
    for ($i = 0; $i -lt $d.modes.Count; $i++) {
        $mode = $d.modes[$i]
        $x = $modeXs[$i % 3]
        $y = $modeYs[[int][Math]::Floor($i / 3)]
        [void](Add-Shape $slide 5 $x $y 280 114 $C.Card $C.Line)
        [void](Add-Shape $slide 1 $x $y 6 114 $modeColors[$i] $modeColors[$i])
        [void](Add-Text $slide $mode.name ($x + 18) ($y + 13) 244 22 12.2 $modeColors[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $mode.plain ($x + 18) ($y + 43) 244 25 10.2 $C.White $false 1 $FontCN 1)
        [void](Add-Text $slide ("输出：" + $mode.output) ($x + 18) ($y + 76) 244 26 9.5 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 430 868 61 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.context 66 442 828 37 11.5 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "“看到新东西”不是单一路径：新增、修订、遮挡、歧义和传感器异常必须产生不同操作。"

    # 11 Four state containers
    $d = $data.slides.states
    $slide = Add-SlideBase $presentation 11 $d.title "状态分层"
    $statePositions = @(
        @{X = 46; Y = 138; W = 224; H = 140; C = $C.Blue},
        @{X = 368; Y = 138; W = 224; H = 140; C = $C.Cyan},
        @{X = 690; Y = 138; W = 224; H = 140; C = $C.Amber},
        @{X = 368; Y = 324; W = 224; H = 125; C = $C.Green}
    )
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $pos = $statePositions[$i]
        [void](Add-Shape $slide 5 $pos.X $pos.Y $pos.W $pos.H $C.Card $C.Line)
        [void](Add-Shape $slide 1 $pos.X $pos.Y 6 $pos.H $pos.C $pos.C)
        [void](Add-Text $slide $item.name ($pos.X + 16) ($pos.Y + 13) ($pos.W - 30) 22 11.5 $pos.C $true 1 $FontCN 1)
        [void](Add-Text $slide $item.cn ($pos.X + 16) ($pos.Y + 40) ($pos.W - 30) 20 10 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $item.role ($pos.X + 16) ($pos.Y + 67) ($pos.W - 22) 39 8.9 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide $item.write ($pos.X + 16) ($pos.Y + 108) ($pos.W - 22) ($pos.H - 115) 8.1 $C.Amber $false 1 $FontCN 1)
    }
    [void](Add-Line $slide 271 208 365 208 $C.Blue 2 $true)
    [void](Add-Text $slide "proposal + executor" 276 184 83 16 7.8 $C.Muted $false 2 $FontMono 1)
    [void](Add-Line $slide 593 208 687 208 $C.Amber 2 $true)
    [void](Add-Text $slide "read-only view" 598 184 83 16 7.8 $C.Muted $false 2 $FontMono 1)
    [void](Add-Line $slide 480 280 480 321 $C.Green 2 $true)
    [void](Add-Text $slide "validated commit" 490 291 92 16 7.8 $C.Muted $false 1 $FontMono 1)
    [void](Add-Shape $slide 5 46 463 868 31 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.rule 58 468 844 21 9.4 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "ActiveContext 的排序变化不得反向删除 SceneBelief；长期记忆只接收已验证版本。"

    # 12 Contribution modules
    $d = $data.slides.contributions
    $slide = Add-SlideBase $presentation 12 $d.title "方法贡献"
    $moduleXs = @(46, 490)
    $moduleYs = @(120, 232, 344)
    $moduleColors = @($C.Blue, $C.Amber, $C.Cyan, $C.Green, $C.Red, $C.Blue)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $x = $moduleXs[$i % 2]
        $y = $moduleYs[[int][Math]::Floor($i / 2)]
        [void](Add-Shape $slide 5 $x $y 424 100 $C.Card $C.Line)
        [void](Add-Shape $slide 1 $x $y 6 100 $moduleColors[$i] $moduleColors[$i])
        [void](Add-Text $slide $item.name ($x + 17) ($y + 11) 386 20 11.3 $moduleColors[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $item.question ($x + 17) ($y + 37) 386 19 9.8 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide ("输出：" + $item.output) ($x + 17) ($y + 61) 386 16 8.9 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide ("防止：" + $item.prevents) ($x + 17) ($y + 80) 386 15 8.9 $C.Amber $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 462 868 32 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.finding 58 467 844 21 10.2 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "每个模块都必须有自己的输入、输出、反例和指标，才能做模块级归因。"

    # 13 WBS
    $d = $data.slides.wbs
    $slide = Add-SlideBase $presentation 13 $d.title "Work Breakdown Structure"
    $topXs = @(46, 268, 490, 712)
    $bottomXs = @(157, 379, 601)
    $wbsColors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green, $C.Blue, $C.Cyan, $C.Amber)
    for ($i = 0; $i -lt $d.packages.Count; $i++) {
        $pkg = $d.packages[$i]
        if ($i -lt 4) {
            $x = $topXs[$i]
            $y = 126
        }
        else {
            $x = $bottomXs[$i - 4]
            $y = 294
        }
        [void](Add-Shape $slide 5 $x $y 202 116 $C.Card $C.Line)
        Add-CircleLabel $slide $pkg.id ($x + 14) ($y + 14) 38 $wbsColors[$i] 10
        [void](Add-Text $slide $pkg.name ($x + 60) ($y + 15) 126 34 10.4 $C.White $true 1 $FontCN 1)
        [void](Add-Line $slide ($x + 16) ($y + 59) ($x + 186) ($y + 59) $C.Line 0.7 $false)
        [void](Add-Text $slide $pkg.deliverable ($x + 16) ($y + 71) 170 34 9.2 $C.Muted $false 1 $FontCN 1)
    }
    for ($i = 0; $i -lt 3; $i++) {
        [void](Add-Line $slide ($topXs[$i] + 203) 184 ($topXs[$i + 1] - 5) 184 $C.Cyan 1.5 $true)
    }
    [void](Add-Line $slide 813 244 258 287 $C.Cyan 1.5 $true)
    for ($i = 0; $i -lt 2; $i++) {
        [void](Add-Line $slide ($bottomXs[$i] + 203) 352 ($bottomXs[$i + 1] - 5) 352 $C.Cyan 1.5 $true)
    }
    [void](Add-Shape $slide 5 46 426 868 29 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.dependency 58 430 844 20 9.8 $C.Cyan $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 463 868 30 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.definition 58 468 844 20 10.2 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "WBS 的对象是工作包和可交付物；椅子、木箱、转角等属于后续 fixture 设计。"

    # 14 Experiment coverage
    $d = $data.slides.experiments
    $slide = Add-SlideBase $presentation 14 $d.title "实验设计审计"
    [void](Add-Shape $slide 5 46 112 868 48 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.current_gap 62 121 836 30 10.5 $C.White $true 2 $FontCN 3)
    $experimentXs = @(46, 264, 482, 700)
    $experimentYs = @(176, 292)
    for ($i = 0; $i -lt $d.tracks.Count; $i++) {
        $track = $d.tracks[$i]
        if ($i -lt 4) {
            $x = $experimentXs[$i]
            $y = $experimentYs[0]
        }
        else {
            $x = 157 + ($i - 4) * 222
            $y = $experimentYs[1]
        }
        [void](Add-Shape $slide 5 $x $y 200 99 $C.Card $C.Line)
        Add-Pill $slide $track.id ($x + 13) ($y + 12) 44 $C.Blue $C.White 9
        [void](Add-Text $slide $track.name ($x + 65) ($y + 13) 119 31 10.2 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $track.goal ($x + 14) ($y + 57) 172 29 9.1 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 407 868 38 $C.Card2 $C.Green)
    [void](Add-Text $slide $d.gate 60 414 840 24 9.8 $C.Green $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 456 868 38 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.status 60 463 840 24 9.5 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "建议覆盖：对齐 → 判型 → operator → scope/stop → version → cross-path/noise；不是只测局部子图。"

    # 15 Decisions before scenarios
    $d = $data.slides.decisions
    $slide = Add-SlideBase $presentation 15 $d.title "下一步研究门"
    [void](Add-Shape $slide 5 46 122 498 330 $C.Card $C.Line)
    [void](Add-Text $slide "需要导师 / 人工确认" 67 141 220 25 14 $C.Amber $true 1 $FontCN 1)
    Add-Bullets $slide $d.items 67 181 449 44 11.2 $C.Amber $C.White
    [void](Add-Shape $slide 5 570 122 344 156 $C.Bg2 $C.Cyan)
    [void](Add-Text $slide "确认后才进入场景" 591 142 290 23 13 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.next 591 180 298 79 11 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 570 299 344 153 $C.Card2 $C.Green)
    [void](Add-Text $slide "本版停点" 591 319 290 23 13 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide "文献边界已压缩；完整方法、状态分流、WBS 与实验覆盖已重构。下一轮再把具体场景映射到这些接口。" 591 356 298 75 11 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 46 466 868 29 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.status 58 470 844 20 9.7 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "下一轮修改场景与 docs/03 前，先确认 D-016 六项人工语义。"

    # Document properties and save
    $outDir = Split-Path -Parent $outputAbs
    if (-not (Test-Path -LiteralPath $outDir)) {
        New-Item -ItemType Directory -Path $outDir | Out-Null
    }
    $presentation.SaveAs($outputAbs, 24)
    Write-Output $outputAbs
}
finally {
    if ($null -ne $presentation) {
        $presentation.Close()
    }
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ppt) | Out-Null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
