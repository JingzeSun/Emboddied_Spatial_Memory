param(
    [string]$ContentPath = "scripts/dynamic_memory_prior_work_ppt_content.json",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v0_7.pptx"
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
    [void](Add-Text $slide "研究设想 · 文献边界 · 方法与验证" 62 68 400 24 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.title 62 112 735 112 33 $C.White $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.subtitle 64 240 680 58 16 $C.Muted $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 62 329 596 72 $C.Card $C.Line)
    [void](Add-Text $slide "本版范围" 80 344 80 20 11 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide "文献基础、方法架构与首轮 oracle 机制验证；不包含实验结果和正式训练。" 169 340 463 42 13.2 $C.White $true 1 $FontCN 3)
    $tags = @("Peer-reviewed foundations", "Controlled write path", "State routing", "Oracle mechanism pilot")
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
    Add-Footer $slide "先冻结概念，再用最小对照实验尝试反驳；本版没有实验结果。"

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
    [void](Add-Text $slide "已经覆盖" 68 249 82 20 10.2 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.covered 157 246 424 37 9.6 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "同一现实场景" 68 289 82 20 10.2 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide $d.farm.scene 157 286 415 38 9.6 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 68 333 230 78 $C.Bg2 $C.Cyan)
    Add-Pill $slide "FARM · query/read" 80 343 136 $C.Cyan $C.Bg 8.5
    [void](Add-Text $slide $d.farm.farm_action 80 374 206 29 8.8 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 310 333 262 78 $C.Bg2 $C.Green)
    Add-Pill $slide "OURS · world revision" 322 343 157 $C.Green $C.Bg 8.5
    [void](Add-Text $slide $d.farm.ours_action 322 372 238 34 8.1 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 68 422 504 46 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.farm.difference 82 429 476 31 9.6 $C.Amber $true 2 $FontCN 3)

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
    Add-Footer $slide "正式基石与预印本分级呈现；Current proposal 的绿色目标不是实验结果。"

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

    # 09 Teacher-facing end-to-end explanation
    $d = $data.slides.pipeline
    $slide = Add-SlideBase $presentation 9 $d.title "核心方法 · 一条主链"
    [void](Add-Text $slide "先把【现在看到什么】和【按旧记忆本来应看到什么】放到同一视角，再决定是否允许写回。" 46 107 868 19 10 $C.Muted $false 1 $FontCN 1)

    [void](Add-Shape $slide 5 46 140 214 76 $C.Card $C.Blue)
    Add-CircleLabel $slide "1" 59 153 32 $C.Blue 9
    [void](Add-Text $slide $d.new_frame 101 151 145 52 9.4 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 46 238 214 76 $C.Card $C.Cyan)
    Add-CircleLabel $slide "2" 59 251 32 $C.Cyan 9
    [void](Add-Text $slide $d.old_view 101 249 145 54 9.2 $C.White $false 1 $FontCN 1)

    [void](Add-Shape $slide 5 300 169 214 116 $C.Card2 $C.Amber)
    Add-CircleLabel $slide "3" 315 184 34 $C.Amber 9
    [void](Add-Text $slide $d.compare 360 184 139 82 10.2 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 263 178 297 202 $C.Blue 1.7 $true)
    [void](Add-Line $slide 263 276 297 246 $C.Cyan 1.7 $true)

    [void](Add-Shape $slide 5 553 169 166 116 $C.Card2 $C.Amber)
    Add-CircleLabel $slide "4" 567 184 34 $C.Amber 9
    [void](Add-Text $slide $d.route 612 184 94 82 9.5 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 517 227 550 227 $C.Amber 1.8 $true)

    [void](Add-Shape $slide 5 758 137 156 82 $C.Card2 $C.Green)
    [void](Add-Text $slide "路径 A" 772 149 48 15 8.3 $C.Green $true 1 $FontMono 1)
    [void](Add-Text $slide $d.world_edit 772 169 128 40 9.1 $C.White $true 1 $FontCN 1)
    [void](Add-Shape $slide 5 758 252 156 82 $C.Card2 $C.Muted)
    [void](Add-Text $slide "路径 B" 772 264 48 15 8.3 $C.Muted $true 1 $FontMono 1)
    [void](Add-Text $slide $d.no_world 772 284 128 40 9.1 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 722 210 755 178 $C.Green 1.7 $true)
    [void](Add-Line $slide 722 246 755 293 $C.Muted 1.7 $true)

    [void](Add-Text $slide "只有路径 A 进入受控写回" 714 338 200 15 8.6 $C.Green $true 2 $FontCN 1)
    [void](Add-Shape $slide 5 718 370 196 76 $C.Card $C.Cyan)
    Add-CircleLabel $slide "5" 731 383 32 $C.Cyan 9
    [void](Add-Text $slide $d.scope 774 381 126 54 8.9 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 506 370 188 76 $C.Card $C.Blue)
    Add-CircleLabel $slide "6" 519 383 32 $C.Blue 9
    [void](Add-Text $slide $d.edit 562 381 118 54 9 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 282 370 200 76 $C.Card $C.Green)
    Add-CircleLabel $slide "7" 295 383 32 $C.Green 9
    [void](Add-Text $slide $d.commit 338 379 130 58 8.8 $C.White $false 1 $FontCN 1)
    [void](Add-Line $slide 914 178 930 178 $C.Green 1.6 $false)
    [void](Add-Line $slide 930 178 930 358 $C.Green 1.6 $false)
    [void](Add-Line $slide 930 358 816 358 $C.Green 1.6 $false)
    [void](Add-Line $slide 816 358 816 367 $C.Green 1.6 $true)
    [void](Add-Line $slide 715 408 697 408 $C.Cyan 1.7 $true)
    [void](Add-Line $slide 503 408 485 408 $C.Blue 1.7 $true)

    [void](Add-Shape $slide 5 46 370 210 76 $C.Card2 $C.Amber)
    [void](Add-Text $slide "查询不是改世界" 60 383 180 18 10.2 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.active 60 407 180 30 8.5 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 46 463 868 33 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.guard 58 469 844 20 9.2 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "一句话讲法：先比较，再分流；只有确需改事实时，才局部、明确、带历史地写回。"

    # 10 Six state paths explained
    $d = $data.slides.routing
    $slide = Add-SlideBase $presentation 10 $d.title "核心方法 · 六条状态路径"
    $gateXs = @(46, 348, 650)
    $gateColors = @($C.Red, $C.Amber, $C.Cyan)
    for ($i = 0; $i -lt 3; $i++) {
        $gate = $d.gates[$i]
        [void](Add-Shape $slide 5 $gateXs[$i] 116 264 86 $C.Card $gateColors[$i])
        Add-CircleLabel $slide ($i + 1) ($gateXs[$i] + 13) 129 32 $gateColors[$i] 9
        [void](Add-Text $slide $gate.name ($gateXs[$i] + 56) 126 194 20 10.5 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $gate.question ($gateXs[$i] + 16) 153 232 17 8.8 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide $gate.fail ($gateXs[$i] + 16) 176 232 17 9.1 $gateColors[$i] $true 1 $FontCN 1)
    }

    $exceptionColors = @($C.Red, $C.Amber)
    for ($i = 0; $i -lt 2; $i++) {
        $path = $d.paths[$i]
        $x = $gateXs[$i]
        [void](Add-Shape $slide 5 $x 216 264 88 $C.Card2 $exceptionColors[$i])
        [void](Add-Text $slide $path.name ($x + 14) 226 236 15 8.6 $exceptionColors[$i] $true 1 $FontMono 1)
        [void](Add-Text $slide $path.cn ($x + 14) 245 236 18 10.8 $C.White $true 1 $FontCN 1)
        $exceptionText = "何时：" + $path.when + [Environment]::NewLine + "处理：" + $path.action + [Environment]::NewLine + "例：" + $path.example
        [void](Add-Text $slide $exceptionText ($x + 14) 266 236 33 7.8 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 650 216 264 88 $C.Card2 $C.Cyan)
    [void](Add-Text $slide "证据可信 + 身份明确" 666 230 232 18 10.5 $C.Cyan $true 2 $FontCN 1)
    [void](Add-Text $slide "这时才比较：是确认旧事实、扩充新内容、反驳旧事实，还是仅仅暂时看不见。" 668 256 228 36 9 $C.White $false 2 $FontCN 1)

    [void](Add-Line $slide 782 306 782 317 $C.Cyan 1.5 $false)
    [void](Add-Line $slide 148 317 804 317 $C.Cyan 1.2 $false)
    $pathXs = @(46, 264, 482, 700)
    $pathColors = @($C.Blue, $C.Green, $C.Red, $C.Cyan)
    for ($i = 2; $i -lt 6; $i++) {
        $path = $d.paths[$i]
        $j = $i - 2
        $x = $pathXs[$j]
        [void](Add-Line $slide ($x + 100) 317 ($x + 100) 326 $C.Cyan 1.2 $true)
        [void](Add-Shape $slide 5 $x 330 200 126 $C.Card $pathColors[$j])
        [void](Add-Text $slide $path.name ($x + 14) 341 172 15 8.4 $pathColors[$j] $true 1 $FontMono 1)
        [void](Add-Text $slide $path.cn ($x + 14) 362 172 19 10.6 $C.White $true 1 $FontCN 1)
        [void](Add-Line $slide ($x + 14) 387 ($x + 186) 387 $C.Line 0.7 $false)
        $pathText = "何时：" + $path.when + [Environment]::NewLine + "处理：" + $path.action + [Environment]::NewLine + "例：" + $path.example
        [void](Add-Text $slide $pathText ($x + 14) 394 172 54 8.1 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 468 868 28 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.guard 56 473 848 18 8.9 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "六条路径回答的是【这次差异该怎样解释和处理】，不是六种数据结构。"

    # 11 Contribution modules
    $d = $data.slides.contributions
    $slide = Add-SlideBase $presentation 11 $d.title "方法贡献"
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

    # 12 Oracle experiment strategy
    $d = $data.slides.experiment_strategy
    $slide = Add-SlideBase $presentation 12 $d.title "验证实验 · 总体策略"
    [void](Add-Shape $slide 5 46 112 868 46 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.question 62 121 836 28 11.2 $C.White $true 2 $FontCN 3)
    $strategyXs = @(46, 350, 654)
    $strategyColors = @($C.Blue, $C.Amber, $C.Green)
    $strategyTitles = @("给定标准答案", "只检验修订机制", "观察是否真的成立")
    $strategyItems = @($d.inputs, $d.mechanism, $d.outputs)
    for ($i = 0; $i -lt 3; $i++) {
        $x = $strategyXs[$i]
        [void](Add-Shape $slide 5 $x 176 260 214 $C.Card $strategyColors[$i])
        Add-CircleLabel $slide ($i + 1) ($x + 16) 191 34 $strategyColors[$i] 9
        [void](Add-Text $slide $strategyTitles[$i] ($x + 62) 194 180 21 11.5 $C.White $true 1 $FontCN 1)
        [void](Add-Line $slide ($x + 16) 235 ($x + 244) 235 $C.Line 0.7 $false)
        Add-Bullets $slide $strategyItems[$i] ($x + 18) 251 224 31 9.3 $strategyColors[$i] $C.Muted
    }
    [void](Add-Line $slide 310 283 344 283 $C.Blue 1.8 $true)
    [void](Add-Line $slide 614 283 648 283 $C.Amber 1.8 $true)
    [void](Add-Shape $slide 5 46 410 868 39 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.principle 60 418 840 24 10.2 $C.Cyan $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 463 868 31 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.status 60 469 840 19 9.6 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "这一步验证的是修订机制，不是视觉感知能力，也不是最终论文性能。"

    # 13 Experiment matrix
    $d = $data.slides.experiment_matrix
    $slide = Add-SlideBase $presentation 13 $d.title "验证实验 · 现实问题"
    [void](Add-Text $slide "实验在问什么" 60 112 250 15 8.4 $C.Muted $true 1 $FontCN 1)
    [void](Add-Text $slide "怎么造这个场景" 330 112 230 15 8.4 $C.Muted $true 1 $FontCN 1)
    [void](Add-Text $slide "正确时应该看到" 575 112 170 15 8.4 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide "失败意味着什么" 760 112 138 15 8.4 $C.Amber $true 1 $FontCN 1)
    $rowColors = @($C.Blue, $C.Amber, $C.Cyan, $C.Green, $C.Red)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $y = 132 + $i * 66
        [void](Add-Shape $slide 5 46 $y 868 58 $C.Card $C.Line)
        [void](Add-Shape $slide 1 46 $y 5 58 $rowColors[$i] $rowColors[$i])
        Add-Pill $slide $item.id 60 ($y + 10) 58 $rowColors[$i] $C.White 8.2
        [void](Add-Text $slide $item.name 128 ($y + 8) 188 19 9.3 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $item.fixtures 128 ($y + 31) 188 18 7.6 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide $item.isolate 330 ($y + 9) 230 39 8.2 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide $item.success 575 ($y + 9) 170 39 8.2 $C.Green $true 1 $FontCN 1)
        [void](Add-Text $slide $item.failure 760 ($y + 9) 138 39 7.8 $C.Amber $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 466 868 28 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.rule 58 471 844 18 8.8 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "五个实验的共同目的：发现方法究竟在哪一种具体情况下会犯错，而不是只给一个总分。"

    # 14 Mechanism baselines
    $d = $data.slides.baselines
    $slide = Add-SlideBase $presentation 14 $d.title "验证实验 · 为什么比较"
    $baselineXsTop = @(46, 345, 644)
    $baselineXsBottom = @(46, 345, 644)
    $baselineColors = @($C.Red, $C.Amber, $C.Blue, $C.Cyan, $C.Green, $C.Cyan)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        if ($i -lt 3) { $x = $baselineXsTop[$i]; $y = 122 } else { $x = $baselineXsBottom[$i - 3]; $y = 276 }
        [void](Add-Shape $slide 5 $x $y 270 132 $C.Card $baselineColors[$i])
        Add-Pill $slide $item.id ($x + 15) ($y + 13) 42 $baselineColors[$i] $C.White 8.8
        [void](Add-Text $slide $item.name ($x + 68) ($y + 11) 184 20 10.8 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide ("论文名：" + $item.alias) ($x + 68) ($y + 36) 184 14 7.4 $C.Muted $false 1 $FontCN 1)
        [void](Add-Line $slide ($x + 16) ($y + 56) ($x + 254) ($y + 56) $C.Line 0.7 $false)
        [void](Add-Text $slide ("它会：" + $item.behavior) ($x + 16) ($y + 64) 238 31 8.5 $C.Muted $false 1 $FontCN 1)
        [void](Add-Text $slide ("拿来检查：" + $item.diagnoses) ($x + 16) ($y + 101) 238 21 8.6 $baselineColors[$i] $true 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 424 868 31 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.shared_input 58 430 844 19 9.3 $C.Cyan $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 465 868 29 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.optional 58 470 844 18 8.3 $C.Amber $false 2 $FontCN 3)
    Add-Footer $slide "这些不是竞争模型名单；每个对照都故意犯一种错误，用来证明我们的方法到底解决了哪件事。"

    # 15 Metrics
    $d = $data.slides.metrics
    $slide = Add-SlideBase $presentation 15 $d.title "验证实验 · 怎么判好坏"
    [void](Add-Shape $slide 5 46 112 868 40 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.summary 58 120 844 23 10.7 $C.Cyan $true 2 $FontCN 3)
    $metricXs = @(46, 490)
    $metricYs = @(168, 316)
    $metricColors = @($C.Green, $C.Cyan, $C.Blue, $C.Amber)
    for ($i = 0; $i -lt $d.groups.Count; $i++) {
        $group = $d.groups[$i]
        $x = $metricXs[$i % 2]
        $y = $metricYs[[int][Math]::Floor($i / 2)]
        [void](Add-Shape $slide 5 $x $y 424 130 $C.Card $metricColors[$i])
        [void](Add-Text $slide $group.name ($x + 18) ($y + 13) 386 20 11.4 $metricColors[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $group.metrics ($x + 18) ($y + 45) 192 65 9.4 $C.White $true 1 $FontCN 1)
        [void](Add-Line $slide ($x + 220) ($y + 42) ($x + 220) ($y + 112) $C.Line 0.8 $false)
        [void](Add-Text $slide "论文里怎么记录" ($x + 240) ($y + 46) 150 16 8.2 $C.Muted $true 1 $FontCN 1)
        [void](Add-Text $slide $group.meaning ($x + 240) ($y + 69) 150 43 8.2 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 465 868 29 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.warning 58 470 844 18 8.8 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "老师先看左边四个问题即可；右边小字只是以后写论文时对应的正式指标名称。"

    # 16 Go / No-Go and oracle removal
    $d = $data.slides.experiment_gates
    $slide = Add-SlideBase $presentation 16 $d.title "验证实验 · 什么时候停止"
    [void](Add-Text $slide "我们到底想证明什么" 60 112 250 15 8.5 $C.Muted $true 1 $FontCN 1)
    [void](Add-Text $slide "至少要看到的现象" 330 112 250 15 8.5 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide "看不到就怎么办" 614 112 270 15 8.5 $C.Red $true 1 $FontCN 1)
    for ($i = 0; $i -lt $d.checks.Count; $i++) {
        $check = $d.checks[$i]
        $y = 133 + $i * 62
        [void](Add-Shape $slide 5 46 $y 868 54 $C.Card $C.Line)
        Add-CircleLabel $slide ($i + 1) 60 ($y + 10) 30 $C.Blue 8.5
        [void](Add-Text $slide $check.comparison 104 ($y + 9) 210 36 8.7 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $check.go 330 ($y + 9) 260 36 8.8 $C.Green $true 1 $FontCN 1)
        [void](Add-Text $slide $check.no_go 614 ($y + 9) 276 36 8.6 $C.Red $false 1 $FontCN 1)
    }
    [void](Add-Text $slide "前一关成立后，再逐步增加难度" 46 450 210 14 8.5 $C.Cyan $true 1 $FontCN 1)
    $progressXs = @(46, 264, 482, 700)
    for ($i = 0; $i -lt $d.progression.Count; $i++) {
        Add-Pill $slide $d.progression[$i] $progressXs[$i] 468 200 $C.Card2 $C.Cyan 8.1
        if ($i -lt 3) { [void](Add-Line $slide ($progressXs[$i] + 202) 480 ($progressXs[$i + 1] - 4) 480 $C.Cyan 1.2 $true) }
    }
    Add-Footer $slide $d.principle

    # 17 Decisions before running fixtures
    $d = $data.slides.decisions
    $slide = Add-SlideBase $presentation 17 $d.title "验证实验 · 判题规则"
    [void](Add-Shape $slide 5 46 122 498 330 $C.Card $C.Line)
    [void](Add-Text $slide "需要老师确认的六条规则" 67 141 280 25 14 $C.Amber $true 1 $FontCN 1)
    Add-Bullets $slide $d.items 67 181 449 44 10.2 $C.Amber $C.White
    [void](Add-Shape $slide 5 570 122 344 156 $C.Bg2 $C.Cyan)
    [void](Add-Text $slide "定完规则就能做" 591 142 290 23 13 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.next 591 180 298 79 11 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 570 299 344 153 $C.Card2 $C.Green)
    [void](Add-Text $slide "本轮状态" 591 319 290 23 13 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide "实验为什么做、每个场景看什么、和哪些笨办法比较、什么结果算失败，都已写清；尚未真正运行实验。" 591 356 310 75 11 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 46 466 868 29 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.status 58 470 844 20 9.7 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "六条规则未确认前，只能讨论实验设计，不能声称已经有唯一正确答案或训练标签。"

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
