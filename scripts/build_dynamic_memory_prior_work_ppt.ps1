param(
    [string]$ContentPath = "scripts/dynamic_memory_prior_work_ppt_content.json",
    [string]$OutputPath = "prototype/dynamic_spatial_revision_report_v0_2.pptx"
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
    # PowerPoint may shrink a newly created textbox back to one line after assigning text.
    # Re-assert the requested bounds so multi-line Chinese content is not clipped.
    $shape.Width = $W
    $shape.Height = $H
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
    [void](Add-Text $slide $Title 46 49 868 42 25 $C.White $true 1 $FontCN 1)
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
    $slide = Add-SlideBase $Presentation $Index $Data.title "结构化文献梳理"
    Add-Pill $slide $Data.year 46 109 210 $C.Blue $C.White 10
    [void](Add-Text $slide $Data.paper 270 107 616 32 10.8 $C.Muted $false 1 $FontCN 3)

    [void](Add-Shape $slide 5 46 151 425 244 $C.Card $C.Line)
    [void](Add-Text $slide "它已经提出" 66 168 180 25 14 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $Data.proposed 66 204 380 44 13.2 $C.Cyan $C.White

    [void](Add-Shape $slide 5 492 151 422 244 $C.Bg2 $C.Line)
    [void](Add-Text $slide "优势" 515 169 55 20 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $Data.strength 577 166 309 55 11.2 $C.White $false 1 $FontCN 1)
    [void](Add-Line $slide 515 228 890 228 $C.Line 0.8 $false)
    [void](Add-Text $slide "局限" 515 245 55 20 12 $C.Red $true 1 $FontCN 1)
    [void](Add-Text $slide $Data.limitation 577 242 309 64 11.2 $C.White $false 1 $FontCN 1)
    [void](Add-Line $slide 515 312 890 312 $C.Line 0.8 $false)
    [void](Add-Text $slide "借鉴" 515 329 55 20 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $Data.borrow 577 326 309 55 11.2 $C.White $false 1 $FontCN 1)

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
    [void](Add-Text $slide "研究设想 · 文献精读 · 实验落地" 62 70 360 24 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.title 62 113 720 112 34 $C.White $true 1 $FontCN 1)
    [void](Add-Text $slide $data.meta.subtitle 64 242 680 48 16 $C.Muted $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 62 322 515 72 $C.Card $C.Line)
    [void](Add-Text $slide "目的" 80 338 62 22 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide "收敛研究问题，核验同行评审边界，并给出可直接启动的 oracle pilot。" 143 334 410 40 14 $C.White $true 1 $FontCN 3)
    $papers = @("Hydra", "Scene Graph Memory", "Khronos", "Embodied VideoAgent", "3DLLM-Mem", "FARM · preprint")
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
    [void](Add-Text $slide "本次汇报完成的收敛" 68 140 260 25 15 $C.Cyan $true 1 $FontCN 1)
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
        [void](Add-Text $slide $it.name ($xs[$i] + 22) 216 220 43 15 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $it.desc ($xs[$i] + 22) 270 232 82 13.2 $C.Muted $false 1 $FontCN 1)
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
    [void](Add-Shape $slide 5 $x0 $y0 868 314 $C.Card $C.Line)
    [void](Add-Text $slide "工作" ($x0 + 10) ($y0 + 17) ($rowNameW - 20) 24 11.5 $C.Muted $true 1 $FontCN 3)
    for ($j = 0; $j -lt $d.columns.Count; $j++) {
        $cx = $x0 + $rowNameW + $j * $colW
        [void](Add-Text $slide $d.columns[$j] ($cx + 4) ($y0 + 8) ($colW - 8) 44 9.2 $C.Muted $true 2 $FontCN 3)
        if ($j -ge 0) { [void](Add-Line $slide $cx $y0 $cx ($y0 + 300) $C.Line 0.7 $false) }
    }
    [void](Add-Line $slide $x0 ($y0 + $headerH) ($x0 + 868) ($y0 + $headerH) $C.Line 1 $false)
    $rowH = 35
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
    [void](Add-Text $slide $d.note 56 457 846 32 9.2 $C.Muted $false 1 $FontCN 1)
    Add-Footer $slide "矩阵依据 5 篇已评审论文与 FARM 预印本；证据等级分开标注。"

    # 12 Overlap
    $d = $data.slides.overlap
    $slide = Add-SlideBase $presentation 12 $d.title "创新性风险"
    [void](Add-Text $slide "已有能力 / 输入" 65 119 180 24 13 $C.Muted $true 1 $FontCN 1)
    [void](Add-Text $slide "在本项目中的位置" 610 119 190 24 13 $C.Muted $true 1 $FontCN 1)
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
    Add-Footer $slide "区分 read / construction / revision 三条路径，避免把已有组件重新包装成方法创新。"

    # 13 Scenarios
    $d = $data.slides.scenarios
    $slide = Add-SlideBase $presentation 13 $d.title "场景与 WBS"
    $scenarioXs = @(46, 264, 482, 700)
    $scenarioYs = @(128, 278)
    $scenarioColors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green, $C.Blue, $C.Cyan, $C.Amber, $C.Green)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $x = $scenarioXs[$i % 4]
        $y = $scenarioYs[[int][Math]::Floor($i / 4)]
        [void](Add-Shape $slide 5 $x $y 200 124 $C.Card $C.Line)
        Add-CircleLabel $slide $item.id ($x + 14) ($y + 14) 38 $scenarioColors[$i] 11
        [void](Add-Text $slide $item.name ($x + 61) ($y + 16) 123 26 12.5 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $item.desc ($x + 18) ($y + 61) 164 45 11 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 422 868 69 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.finding 68 435 824 43 12.3 $C.Cyan $true 1 $FontCN 3)
    Add-Footer $slide "每个 fixture：base graph + observation + oracle delta + expected graph + counterfactual + provenance。"

    # 14 Oracle pilot
    $d = $data.slides.pilot
    $slide = Add-SlideBase $presentation 14 $d.title "实验方案"
    [void](Add-Shape $slide 5 46 123 500 359 $C.Card $C.Line)
    [void](Add-Text $slide "实验顺序" 67 140 140 24 14 $C.Cyan $true 1 $FontCN 1)
    for ($i = 0; $i -lt $d.phases.Count; $i++) {
        $phase = $d.phases[$i]
        $yy = 177 + $i * 57
        Add-CircleLabel $slide $phase.id 67 $yy 34 $C.Blue 10
        [void](Add-Text $slide $phase.name 114 ($yy - 1) 165 20 11.7 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $phase.goal 285 ($yy - 1) 235 35 10.5 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 570 123 344 101 $C.Bg2 $C.Line)
    [void](Add-Text $slide "机制基线" 590 139 100 20 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.baselines 590 168 304 44 10.4 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 570 238 344 112 $C.Bg2 $C.Line)
    [void](Add-Text $slide "核心指标" 590 254 100 20 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.metrics 590 283 304 53 10.4 $C.White $false 1 $FontCN 1)
    [void](Add-Shape $slide 5 570 365 344 117 $C.Card2 $C.Green)
    [void](Add-Text $slide "Go / No-Go" 590 381 120 20 12 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide $d.gate 590 409 304 58 10.7 $C.White $false 1 $FontCN 1)
    Add-Footer $slide "若 oracle 输入下机制不成立：修合同/执行器或收缩 claim，不用训练掩盖问题。"

    # 15 Training
    $d = $data.slides.training
    $slide = Add-SlideBase $presentation 15 $d.title "训练与正式评测"
    $trainXs = @(46, 340, 634)
    $trainYs = @(129, 265)
    for ($i = 0; $i -lt $d.stages.Count; $i++) {
        $stage = $d.stages[$i]
        $x = $trainXs[$i % 3]
        $y = $trainYs[[int][Math]::Floor($i / 3)]
        [void](Add-Shape $slide 5 $x $y 280 105 $C.Card $C.Line)
        Add-Pill $slide $stage.id ($x + 17) ($y + 15) 46 $C.Blue $C.White 10
        [void](Add-Text $slide $stage.name ($x + 76) ($y + 16) 184 24 12.5 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $stage.desc ($x + 18) ($y + 57) 244 28 10.8 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 391 868 45 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.rule 65 400 830 28 11.4 $C.Amber $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 447 868 43 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.after 65 455 830 27 11.2 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "顺序：innovation → scope → operator/stop → association ambiguity → noisy perception → scenario generalization。"

    # 16 Term glossary
    $d = $data.slides.term_glossary
    $slide = Add-SlideBase $presentation 16 $d.title "答辩术语"
    $termXs = @(46, 264, 482, 700)
    $termYs = @(123, 274)
    $termColors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green, $C.Blue, $C.Cyan, $C.Amber, $C.Green)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $x = $termXs[$i % 4]
        $y = $termYs[[int][Math]::Floor($i / 4)]
        [void](Add-Shape $slide 5 $x $y 200 132 $C.Card $C.Line)
        [void](Add-Shape $slide 1 $x $y 6 132 $termColors[$i] $termColors[$i])
        [void](Add-Text $slide $item.term ($x + 17) ($y + 14) 168 23 11.8 $termColors[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $item.plain ($x + 17) ($y + 44) 180 39 9.2 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide ("例：" + $item.scene) ($x + 17) ($y + 88) 168 34 8.8 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 425 868 66 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.answer 68 440 824 37 12.2 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "答题模板：它解决什么问题 → 举一个场景 → 说明怎样判错。"

    # 17 State glossary
    $d = $data.slides.state_glossary
    $slide = Add-SlideBase $presentation 17 $d.title "状态分层"
    $stateXs = @(46, 490)
    $stateYs = @(124, 294)
    $stateColors = @($C.Blue, $C.Cyan, $C.Amber, $C.Green)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $x = $stateXs[$i % 2]
        $y = $stateYs[[int][Math]::Floor($i / 2)]
        [void](Add-Shape $slide 5 $x $y 424 153 $C.Card $C.Line)
        Add-Pill $slide $item.name ($x + 18) ($y + 16) 165 $stateColors[$i] $C.White 10
        [void](Add-Text $slide $item.cn ($x + 198) ($y + 18) 198 22 12 $stateColors[$i] $true 1 $FontCN 1)
        [void](Add-Text $slide $item.plain ($x + 19) ($y + 57) 386 35 10.6 $C.White $false 1 $FontCN 1)
        [void](Add-Text $slide ("场景：" + $item.example) ($x + 19) ($y + 101) 386 38 9.5 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 462 868 30 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.rule 59 467 842 20 10.5 $C.Cyan $true 2 $FontCN 3)
    Add-Footer $slide "核心边界：ActiveContext 的排序变化不得删除或覆盖 SceneBelief 中未选中的实例。"

    # 18 WBS explainer
    $d = $data.slides.wbs_explainer
    $slide = Add-SlideBase $presentation 18 $d.title "WBS 执行动作"
    [void](Add-Shape $slide 5 46 119 868 61 $C.Card2 $C.Cyan)
    [void](Add-Text $slide $d.definition 65 130 830 39 11.2 $C.White $true 1 $FontCN 3)
    $wbsXs = @(46, 340, 634)
    $wbsYs = @(196, 306)
    for ($i = 0; $i -lt $d.steps.Count; $i++) {
        $step = $d.steps[$i]
        $x = $wbsXs[$i % 3]
        $y = $wbsYs[[int][Math]::Floor($i / 3)]
        [void](Add-Shape $slide 5 $x $y 280 96 $C.Card $C.Line)
        Add-CircleLabel $slide $step.id ($x + 14) ($y + 14) 34 $C.Blue 10
        [void](Add-Text $slide $step.name ($x + 60) ($y + 15) 198 22 11.8 $C.White $true 1 $FontCN 1)
        [void](Add-Text $slide $step.desc ($x + 18) ($y + 50) 260 34 9.6 $C.Muted $false 1 $FontCN 1)
    }
    [void](Add-Shape $slide 5 46 419 868 33 $C.Card2 $C.Amber)
    [void](Add-Text $slide $d.deliverables 59 425 842 21 9.8 $C.Amber $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 460 868 32 $C.Card2 $C.Green)
    [void](Add-Text $slide $d.not_now 59 466 842 20 10.3 $C.Green $true 2 $FontCN 3)
    Add-Footer $slide "WBS 的验收：不看实现代码，只看 fixture 就能写出正确输出与反例。"

    # 19 Fixture walkthrough
    $d = $data.slides.fixture_walkthrough
    $slide = Add-SlideBase $presentation 19 $d.title "R1 完整示例"
    [void](Add-Shape $slide 5 46 121 410 254 $C.Card $C.Line)
    [void](Add-Text $slide "1 旧世界" 66 139 92 20 12 $C.Blue $true 1 $FontCN 1)
    [void](Add-Text $slide $d.base 165 136 267 43 10.5 $C.White $false 1 $FontCN 1)
    [void](Add-Line $slide 66 190 432 190 $C.Line 0.8 $false)
    [void](Add-Text $slide "2 新观测" 66 207 92 20 12 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.observation 165 204 267 58 10.5 $C.White $false 1 $FontCN 1)
    [void](Add-Line $slide 66 276 432 276 $C.Line 0.8 $false)
    [void](Add-Text $slide "3 判类型" 66 293 92 20 12 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.innovation 165 290 267 58 10.5 $C.White $false 1 $FontCN 1)

    [void](Add-Shape $slide 5 478 121 436 254 $C.Bg2 $C.Line)
    [void](Add-Text $slide "4 人工标准答案：oracle_delta" 499 139 300 22 13 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $d.operations 499 176 385 37 10.5 $C.Cyan $C.White

    [void](Add-Shape $slide 5 46 391 868 99 $C.Card2 $C.Green)
    [void](Add-Text $slide "正确输出" 64 404 80 18 10.5 $C.Green $true 1 $FontCN 1)
    [void](Add-Text $slide $d.expected 151 401 741 24 10.1 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "反事实" 64 434 80 18 10.5 $C.Amber $true 1 $FontCN 1)
    [void](Add-Text $slide $d.counterfactual 151 431 741 24 10.1 $C.White $false 1 $FontCN 1)
    [void](Add-Text $slide "判分" 64 464 80 18 10.5 $C.Cyan $true 1 $FontCN 1)
    [void](Add-Text $slide $d.score 151 461 741 22 10.1 $C.White $false 1 $FontCN 1)
    Add-Footer $slide "R1 的唯一关键变量是 identity；其它场景分别只改变 visibility、dependency、relevance 或 history。"

    # 20 Common questions
    $d = $data.slides.qa
    $slide = Add-SlideBase $presentation 20 $d.title "口头回答"
    $qaXs = @(46, 490)
    $qaYs = @(121, 244, 367)
    for ($i = 0; $i -lt $d.items.Count; $i++) {
        $item = $d.items[$i]
        $x = $qaXs[$i % 2]
        $y = $qaYs[[int][Math]::Floor($i / 2)]
        [void](Add-Shape $slide 5 $x $y 424 106 $C.Card $C.Line)
        [void](Add-Text $slide ("Q  " + $item.q) ($x + 18) ($y + 13) 388 24 11.5 $C.Amber $true 1 $FontCN 1)
        [void](Add-Text $slide ("A  " + $item.a) ($x + 18) ($y + 46) 388 50 10.2 $C.White $false 1 $FontCN 1)
    }
    Add-Footer $slide "回答时不要背缩写；先说现实失败案例，再说这个概念怎样阻止该失败。"

    # 21 Close
    $d = $data.slides.close
    $slide = Add-SlideBase $presentation 21 $d.title "结论"
    [void](Add-Shape $slide 5 46 121 868 73 $C.Card2 $C.Red)
    [void](Add-Text $slide $d.headline 70 135 820 44 16.5 $C.White $true 2 $FontCN 3)
    [void](Add-Shape $slide 5 46 216 410 244 $C.Card $C.Line)
    [void](Add-Text $slide "需要导师 / 人工确认" 67 234 210 24 14 $C.Amber $true 1 $FontCN 1)
    Add-Bullets $slide $d.human_confirm 67 270 360 30 10.8 $C.Amber $C.White
    [void](Add-Shape $slide 5 478 216 436 244 $C.Card $C.Line)
    [void](Add-Text $slide "下一轮执行顺序" 499 234 180 24 14 $C.Cyan $true 1 $FontCN 1)
    Add-Bullets $slide $d.next 499 278 385 42 12.1 $C.Cyan $C.White
    [void](Add-Text $slide $d.footer 46 469 868 25 11.5 $C.Amber $true 2 $FontCN 3)
    Add-Footer $slide "Research integrity：已接受合同 ≠ 已实现；oracle pilot ≠ 正式实验；preprint ≠ 同行评审基石。"

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
