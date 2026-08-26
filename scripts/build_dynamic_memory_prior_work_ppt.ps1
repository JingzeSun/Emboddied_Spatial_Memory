param(
    [string]$ContentPath = "scripts/dynamic_memory_prior_work_ppt_content.json",
    [string]$OutputPath = "prototype/dynamic_memory_prior_work_review_zh.pptx"
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
    Dark = Rgb 7 12 22
}

$FontCN = "Microsoft YaHei"
$FontMono = "Consolas"
$SlideW = 960
$SlideH = 540

function Add-Shape {
    param($Slide, [int]$Type, [double]$X, [double]$Y, [double]$W, [double]$H,
          [int]$Fill, [int]$Line, [double]$Radius = 0, [double]$Transparency = 0)
    $shape = $Slide.Shapes.AddShape($Type, $X, $Y, $W, $H)
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $Fill
    $shape.Fill.Transparency = [Math]::Min(1.0, [Math]::Max(0.0, $Transparency / 100.0))
    $shape.Line.ForeColor.RGB = $Line
    $shape.Line.Weight = 1
    return $shape
}

function Add-Text {
    param($Slide, [string]$Text, [double]$X, [double]$Y, [double]$W, [double]$H,
          [double]$Size = 16, [int]$Color = $C.White, [bool]$Bold = $false,
          [int]$Align = 1, [string]$Font = $FontCN, [int]$VAnchor = 1)
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
    return $shape
}

function Add-Line {
    param($Slide, [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
          [int]$Color = $C.Line, [double]$Weight = 1.5, [bool]$Arrow = $false)
    $line = $Slide.Shapes.AddLine($X1, $Y1, $X2, $Y2)
    $line.Line.ForeColor.RGB = $Color
    $line.Line.Weight = $Weight
    if ($Arrow) { $line.Line.EndArrowheadStyle = 3 }
    return $line
}

function Add-CircleLabel {
    param($Slide, [string]$Text, [double]$X, [double]$Y, [double]$D,
          [int]$Fill = $C.Blue, [double]$Size = 13)
    [void](Add-Shape $Slide 9 $X $Y $D $D $Fill $Fill)
    [void](Add-Text $Slide $Text $X $Y $D $D $Size $C.White $true 2 $FontCN 3)
}

function Add-Pill {
    param($Slide, [string]$Text, [double]$X, [double]$Y, [double]$W,
          [int]$Fill = $C.Card2, [int]$Color = $C.Cyan, [double]$Size = 11)
    [void](Add-Shape $Slide 5 $X $Y $W 26 $Fill $Fill)
    [void](Add-Text $Slide $Text ($X + 8) ($Y + 1) ($W - 16) 24 $Size $Color $true 2 $FontCN 3)
}

function Add-SlideBase {
    param($Presentation, [int]$Index, [string]$Title, [string]$Section)
    $slide = $Presentation.Slides.Add($Index, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $C.Bg
    [void](Add-Shape $slide 1 0 0 10 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide $Section 46 28 180 16 9 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $Title 46 49 850 42 25 $C.White $true 1 $FontCN 1)
    [void](Add-Line $slide 46 97 914 97 $C.Line 1 $false)
    [void](Add-Text $slide ("{0:D2}" -f $Index) 886 28 28 18 9 $C.Muted $true 2 $FontMono 1)
    return $slide
}

function Add-Footer {
    param($Slide, [string]$Text)
    [void](Add-Line $Slide 46 509 914 509 $C.Line 0.8 $false)
    [void](Add-Text $Slide $Text 46 515 868 13 7.5 $C.Muted $false 1 $FontCN 1)
}

function Add-Bullets {
    param($Slide, $Items, [double]$X, [double]$Y, [double]$W,
          [double]$Gap = 48, [double]$Size = 14, [int]$BulletColor = $C.Cyan,
          [int]$TextColor = $C.White)
    $i = 0
    foreach ($item in $Items) {
        $yy = $Y + $i * $Gap
        [void](Add-Shape $Slide 9 $X ($yy + 6) 9 9 $BulletColor $BulletColor)
        [void](Add-Text $Slide ([string]$item) ($X + 19) $yy ($W - 19) ($Gap - 4) $Size $TextColor $false 1 $FontCN 1)
        $i++
    }
}

function Add-TagRow {
    param($Slide, $Tags, [double]$X, [double]$Y, [double]$MaxW)
    $cx = $X
    foreach ($tag in $Tags) {
        $w = [Math]::Min(150, 26 + ([string]$tag).Length * 13)
        if ($cx + $w -gt $X + $MaxW) { break }
        Add-Pill $Slide ([string]$tag) $cx $Y $w $C.Card2 $C.Cyan 10.5
        $cx += $w + 8
    }
}

function Add-Node {
    param($Slide, [string]$Text, [double]$X, [double]$Y, [double]$W, [double]$H,
          [int]$Accent = $C.Blue, [double]$Size = 13)
    [void](Add-Shape $Slide 5 $X $Y $W $H $C.Card2 $Accent)
    [void](Add-Shape $Slide 1 $X $Y 5 $H $Accent $Accent)
    [void](Add-Text $Slide $Text ($X + 13) ($Y + 3) ($W - 20) ($H - 6) $Size $C.White $true 2 $FontCN 3)
}

function Add-PaperCommon {
    param($Presentation, [int]$Index, $Data, [string]$Code, [scriptblock]$Diagram)
    $slide = Add-SlideBase $Presentation $Index $Data.title "近邻工作"
    Add-Pill $slide $Data.year 46 109 98 $C.Blue $C.White 11
    [void](Add-Text $slide $Data.paper 158 107 728 32 11.5 $C.Muted $false 1 $FontCN 3)

    [void](Add-Shape $slide 5 46 151 425 244 $C.Card $C.Line)
    [void](Add-Text $slide "它已经提出" 66 168 180 25 14 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $Data.proposed 66 204 380 44 13.2 $C.Cyan $C.White

    [void](Add-Shape $slide 5 492 151 422 244 $C.Bg2 $C.Line)
    & $Diagram $slide
    [void](Add-Text $slide "对原设想的直接覆盖" 515 333 200 18 11 $C.Muted $true 1 $FontCN 1)
    Add-TagRow $slide $Data.overlap 515 358 376

    [void](Add-Shape $slide 5 46 414 868 76 $C.Card $C.Line)
    [void](Add-Text $slide "边界" 66 428 54 20 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $Data.boundary 125 425 755 47 12.2 $C.White $false 1 $FontCN 1)
    Add-Footer $slide ("来源：" + $Data.source)
    return $slide
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contentAbs = if ([System.IO.Path]::IsPathRooted($ContentPath)) { $ContentPath } else { Join-Path $root $ContentPath }
$outputAbs = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $root $OutputPath }
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
    [void](Add-Shape $slide 9 664 -110 420 420 $C.Blue $C.Blue 0 84)
    [void](Add-Shape $slide 9 740 208 300 300 $C.Cyan $C.Cyan 0 90)
    [void](Add-Shape $slide 1 0 0 12 $SlideH $C.Blue $C.Blue)
    [void](Add-Text $slide "文献核查 · 2023—2026" 62 70 300 24 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.title 62 113 720 112 34 $C.White $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.subtitle 64 242 680 48 16 $C.Muted $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 62 322 515 72 $C.Card $C.Line)
    [void](Add-Text $slide "目的" 80 338 62 22 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide "先证明哪些概念已经被提出，再决定还能从哪里形成真正的新问题。" 143 334 410 40 14 $C.White $true 1 $FontCN 3)
    $papers = @("KARMA", "Khronos", "Embodied VideoAgent", "DYNEMO-SLAM", "R4DSG", "Scene Graph Memory")
    $px = 62
    foreach ($p in $papers) {
        $pw = 24 + $p.Length * 8.2
        if ($px + $pw -gt 890) { $px = 62 }
        Add-Pill $slide $p $px 432 $pw $C.Card2 $C.Cyan 9.5
        $px += $pw + 8
    }
    [void](Add-Text $slide ($data.meta.date + "  ·  " + $data.meta.author) 62 496 400 18 9 $C.Muted $false 1 $FontCN 1)

    # 02 Thesis
    $d = $data.slides.thesis
    $slide = Add-SlideBase $presentation 2 $d.title "原始设想复盘"
    [void](Add-Shape $slide 5 46 119 544 276 $C.Card $C.Line)
    [void](Add-Text $slide "当前动态模块的实际职责" 68 140 260 25 15 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $d.original 68 181 485 44 13.8 $C.Cyan $C.White
    [void](Add-Shape $slide 5 46 416 544 68 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.finding 67 429 500 40 14 $C.Amber $true 1 $FontCN 3)
    $imagePath = Join-Path $root "prototype/d94b8f8b-74ab-4317-b876-f93e568bbbd8.png"
    [void](Add-Shape $slide 5 622 119 292 365 $C.White $C.Line)
    $pic = $slide.Shapes.AddPicture($imagePath, 0, -1, 638, 132, 259, 340)
    $pic.LockAspectRatio = -1
    Add-Footer $slide $d.source

    # 03 Taxonomy
    $d = $data.slides.taxonomy
    $slide = Add-SlideBase $presentation 3 $d.title "概念澄清"
    $xs = @(46, 346, 646)
    $accents = @($C.Blue, $C.Cyan, $C.Amber)
    for ($i = 0; $i -lt 3; $i++) {
        $it = $d.items[$i]
        [void](Add-Shape $slide 5 $xs[$i] 132 268 245 $C.Card $C.Line)
        Add-CircleLabel $slide $it.label ($xs[$i] + 22) 153 48 $accents[$i] 12
        [void](Add-Text $slide $it.name ($xs[$i] + 22) 216 220 30 17 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $it.desc ($xs[$i] + 22) 264 222 89 13.2 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 407 868 76 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.finding 70 420 820 48 15 $C.Cyan $true 1 $FontCN 3)
    Add-Footer $slide "概念说明：运动状态、时间持久性与记忆生命周期不能互相替代。"

    # 04 Timeline
    $d = $data.slides.timeline
    $slide = Add-SlideBase $presentation 4 $d.title "能力演进"
    [void](Add-Line $slide 88 282 872 282 $C.Line 3 $false)
    $positions = @(92, 244, 396, 548, 700, 852)
    for ($i = 0; $i -lt 6; $i++) {
        $ev = $d.events[$i]
        $x = $positions[$i]
        $top = ($i % 2 -eq 0)
        Add-CircleLabel $slide "" ($x - 9) 273 18 $C.Cyan 1
        if ($top) {
            [void](Add-Line $slide $x 273 $x 218 $C.Line 1.5 $false)
            [void](Add-Text $slide $ev.year ($x - 45) 121 90 20 11 $C.Amber $true 2 $FontMono 1)
            [void](Add-Text $slide $ev.paper ($x - 65) 147 130 28 12.5 $C.White $true 2 $FontCN 1)
            [void](Add-Text $slide $ev.claim ($x - 65) 179 130 40 10.5 $C.Muted $false 2 $FontCN 1)
        } else {
            [void](Add-Line $slide $x 291 $x 342 $C.Line 1.5 $false)
            [void](Add-Text $slide $ev.year ($x - 45) 354 90 20 11 $C.Amber $true 2 $FontMono 1)
            [void](Add-Text $slide $ev.paper ($x - 66) 380 132 28 12.5 $C.White $true 2 $FontCN 1)
            [void](Add-Text $slide $ev.claim ($x - 66) 412 132 42 10.5 $C.Muted $false 2 $FontCN 1)
        }
    }
    Add-Footer $slide $d.source

    # 05 KARMA
    $d = $data.slides.karma
    [void](Add-PaperCommon $presentation 5 $d "KARMA" {
        param($s)
        Add-Node $s "长期 3D Scene Graph" 535 181 150 57 $C.Blue 12.5
        Add-Node $s "短期对象状态" 535 263 150 57 $C.Cyan 12.5
        [void](Add-Line $s 700 210 763 239 $C.Line 2 $true)
        [void](Add-Line $s 700 292 763 253 $C.Line 2 $true)
        Add-Node $s "LLM Planner" 765 220 112 63 $C.Amber 13
    })

    # 06 Khronos
    $d = $data.slides.khronos
    [void](Add-PaperCommon $presentation 6 $d "Khronos" {
        param($s)
        Add-Node $s "Active Window\n短期 fragments" 516 181 120 66 $C.Cyan 11.5
        [void](Add-Line $s 641 214 685 214 $C.Line 2 $true)
        Add-Node $s "Global`nOptimization" 691 181 105 66 $C.Blue 11.5
        [void](Add-Line $s 801 214 835 214 $C.Line 2 $true)
        Add-Node $s "Object / Map`nReconcile" 820 181 82 66 $C.Amber 9.5
        [void](Add-Text $s "快过程" 532 273 90 18 10 $C.Cyan $true 2 $FontCN 1)
        [void](Add-Text $s "慢过程" 710 273 90 18 10 $C.Blue $true 2 $FontCN 1)
    })

    # 07 VideoAgent
    $d = $data.slides.videoagent
    [void](Add-PaperCommon $presentation 7 $d "VideoAgent" {
        param($s)
        Add-Node $s "RGB + Depth + Pose" 516 174 133 48 $C.Blue 11.5
        [void](Add-Line $s 654 198 700 198 $C.Line 2 $true)
        Add-Node $s "Persistent Object\nMemory" 706 167 155 62 $C.Cyan 12
        Add-Node $s "3D re-ID" 530 259 105 45 $C.Cyan 11.5
        Add-Node $s "VLM Action Update" 674 259 177 45 $C.Amber 11.5
        [void](Add-Line $s 583 252 720 228 $C.Line 1.5 $true)
        [void](Add-Line $s 764 252 778 229 $C.Line 1.5 $true)
    })

    # 08 DYNEMO
    $d = $data.slides.dynemo
    [void](Add-PaperCommon $presentation 8 $d "DYNEMO" {
        param($s)
        Add-CircleLabel $s "R" 548 219 50 $C.Blue 17
        Add-CircleLabel $s "E" 742 178 50 $C.Cyan 17
        Add-CircleLabel $s "P" 742 272 50 $C.Amber 17
        [void](Add-Line $s 600 237 741 198 $C.Cyan 2.5 $true)
        [void](Add-Line $s 600 248 741 292 $C.Amber 2.5 $true)
        [void](Add-Line $s 767 226 767 271 $C.Line 2 $true)
        [void](Add-Text $s "Robot pose" 522 282 100 18 10 $C.Muted $false 2 $FontCN 1)
        [void](Add-Text $s "Dynamic entity" 705 148 125 18 10 $C.Muted $false 2 $FontCN 1)
        [void](Add-Text $s "Plane / structure" 700 323 135 18 10 $C.Muted $false 2 $FontCN 1)
    })

    # 09 R4DSG
    $d = $data.slides.r4dsg
    [void](Add-PaperCommon $presentation 9 $d "R4DSG" {
        param($s)
        Add-Node $s "Stable Anchor\n桌 / 房间" 522 210 128 62 $C.Blue 11.5
        [void](Add-Line $s 655 241 711 241 $C.Line 2 $true)
        Add-Node $s "Dynamic Object\n持续身份" 717 210 140 62 $C.Cyan 11.5
        Add-Pill $s "t0 → t1：anchor-relative change" 548 295 282 $C.Card2 $C.Amber 10.5
        [void](Add-Text $s "不依赖完整全局 world frame" 565 181 250 18 10 $C.Muted $false 2 $FontCN 1)
    })

    # 10 SGM
    $d = $data.slides.sgm
    [void](Add-PaperCommon $presentation 10 $d "SGM" {
        param($s)
        Add-Node $s "Room" 526 180 82 44 $C.Blue 11.5
        Add-Node $s "Object A" 526 267 82 44 $C.Cyan 11.5
        Add-Node $s "Object B" 656 267 82 44 $C.Cyan 11.5
        [void](Add-Line $s 567 225 567 266 $C.Line 1.8 $true)
        [void](Add-Line $s 599 217 689 266 $C.Line 1.8 $true)
        [void](Add-Line $s 745 289 790 247 $C.Line 2 $true)
        Add-Node $s "Node Edge\nPredictor" 796 213 94 66 $C.Amber 10.5
        [void](Add-Text $s "历史观测 → 对象位置概率" 598 330 220 18 10 $C.Muted $false 2 $FontCN 1)
    })

    # 11 Matrix
    $d = $data.slides.matrix
    $slide = Add-SlideBase $presentation 11 $d.title "横向比较"
    $x0 = 46
    $rowNameW = 176
    $colW = 98.8
    $y0 = 132
    $headerH = 58
    [void](Add-Shape $slide 5 $x0 $y0 868 339 $C.Card $C.Line)
    [void](Add-Text $slide "工作" ($x0 + 10) ($y0 + 17) ($rowNameW - 20) 24 11.5 $C.Muted $true 1 $FontCN 3)
    for ($j = 0; $j -lt $d.columns.Count; $j++) {
        $cx = $x0 + $rowNameW + $j * $colW
        [void](Add-Text $slide $d.columns[$j] ($cx + 4) ($y0 + 8) ($colW - 8) 44 9.2 $C.Muted $true 2 $FontCN 3)
        if ($j -ge 0) { [void](Add-Line $slide $cx $y0 $cx ($y0 + 300) $C.Line 0.7 $false) }
    }
    [void](Add-Line $slide $x0 ($y0 + $headerH) ($x0 + 868) ($y0 + $headerH) $C.Line 1 $false)
    $rowH = 40
    for ($i = 0; $i -lt $d.rows.Count; $i++) {
        $row = $d.rows[$i]
        $ry = $y0 + $headerH + $i * $rowH
        if ($i % 2 -eq 1) { [void](Add-Shape $slide 1 ($x0 + 1) $ry 866 $rowH $C.Bg2 $C.Bg2) }
        [void](Add-Text $slide $row.paper ($x0 + 12) ($ry + 8) ($rowNameW - 18) 24 10.5 $C.White $true 1 $FontCN 3)
        for ($j = 0; $j -lt $row.values.Count; $j++) {
            $val = [string]$row.values[$j]
            $color = if ($val -eq "✓") { $C.Cyan } elseif ($val -eq "△") { $C.Amber } else { $C.Muted }
            $cx = $x0 + $rowNameW + $j * $colW
            [void](Add-Text $slide $val $cx ($ry + 5) $colW 28 16 $color $true 2 $FontCN 3)
        }
        [void](Add-Line $slide $x0 ($ry + $rowH) ($x0 + 868) ($ry + $rowH) $C.Line 0.45 $false)
    }
    [void](Add-Text $slide $d.note 56 445 846 36 9.2 $C.Muted $false 1 $FontCN 1)
    Add-Footer $slide "矩阵依据六篇论文原文；只比较本次审查涉及的宽泛动态记忆能力。"

    # 12 Overlap
    $d = $data.slides.overlap
    $slide = Add-SlideBase $presentation 12 $d.title "创新性风险"
    [void](Add-Text $slide "原始构想" 65 119 180 24 13 $C.Muted $true 1 $FontCN 1)
    [void](Add-Text $slide "已有直接覆盖" 610 119 190 24 13 $C.Muted $true 1 $FontCN 1)
    $colors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green, $C.Blue, $C.Cyan)
    for ($i = 0; $i -lt $d.mappings.Count; $i++) {
        $m = $d.mappings[$i]
        $yy = 154 + $i * 48
        Add-Node $slide $m.idea 54 $yy 300 35 $colors[$i] 11.2
        [void](Add-Line $slide 360 ($yy + 17) 572 ($yy + 17) $colors[$i] 1.8 $true)
        Add-Node $slide $m.papers 582 $yy 324 35 $colors[$i] 10.8
    }
    [void](Add-Shape $slide 5 54 451 852 42 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.finding 70 458 820 28 12 $C.Red $true 2 $FontCN 3)
    Add-Footer $slide "结论是概念级新颖性不足，不等价于这些论文已经解决本项目的全部技术问题。"

    # 13 Close
    $d = $data.slides.close
    $slide = Add-SlideBase $presentation 13 $d.title "结论"
    [void](Add-Shape $slide 5 46 121 868 73 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.headline 70 135 820 44 17 $C.White $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 216 410 232 $C.Card $C.Line)
    [void](Add-Text $slide "不能再声称" 67 236 160 24 14 $C.Red $true 1 $FontCN 1)
    Add-Bullets $slide $d.cannot_claim 67 278 360 41 12.4 $C.Red $C.White
    [void](Add-Shape $slide 5 478 216 436 232 $C.Card $C.Line)
    [void](Add-Text $slide "下一轮必须回答" 499 236 180 24 14 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $d.next 499 278 385 41 12.4 $C.Cyan $C.White
    [void](Add-Text $slide $d.footer 46 469 868 25 12 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "Research integrity note: 已提出、未解决和计划中必须在后续稿件中明确区分。"

    # Document properties and save
    $outDir = Split-Path -Parent $outputAbs
    if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
    $presentation.SaveAs($outputAbs, 24)
    Write-Output $outputAbs
}
finally {
    if ($null -ne $presentation) { $presentation.Close() }
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ppt) | Out-Null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
