param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$PackageMode,
    [switch]$AllowGitMetadata
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$violations = New-Object System.Collections.Generic.List[string]

function Add-Violation {
    param([string]$Message)
    $violations.Add($Message) | Out-Null
}

function Get-RelativePath {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $base = [System.IO.Path]::GetFullPath($rootPath)
    if (-not $base.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $base = $base + [System.IO.Path]::DirectorySeparatorChar
    }
    if ($full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($base.Length)
    }
    return $full
}

function Test-AllowedPublicFile {
    param([System.IO.FileInfo]$File)

    $name = $File.Name
    if ($name -in @(
        "README.md",
        "公开样板说明.md",
        "联系入口模板.md",
        "成品文案输入模板.md",
        "00_手动输入选题表.md",
        "00_手动输入选题表模板.md",
        "00_原始资料输入清单.md",
        "00_原始资料输入清单模板.md",
        "输入说明.md",
        "输入要求说明.md",
        "字段模板.md",
        "00_爆款开头选中清单模板.md",
        "字段说明.md"
    )) {
        return $true
    }

    if ($name.StartsWith("样板-")) {
        return $true
    }

    if ($name.EndsWith("模板.md")) {
        return $true
    }

    if ($File.DirectoryName -like "*\参考案例" -and $name.StartsWith("案例-") -and $File.Extension -eq ".md") {
        return $true
    }

    return $false
}

function Assert-NoForbiddenTopLevel {
    $forbiddenTopLevel = @(
        "_private",
        ".agents",
        ".codex",
        ".obsidian",
        "讲干货-AI流量工厂",
        "热门播客-AI流量工厂",
        "推荐型-AI流量工厂"
    )

    if (-not $AllowGitMetadata) {
        $forbiddenTopLevel += ".git"
    }

    foreach ($name in $forbiddenTopLevel) {
        $candidate = Join-Path $rootPath $name
        if (Test-Path -LiteralPath $candidate) {
            Add-Violation "公开发布包不允许包含顶层目录或文件: $name"
        }
    }
}

function Assert-PublicAssetDirectoriesClean {
    $assetDirs = @(
        "02_资产中心\01_原始知识库",
        "02_资产中心\02_内容模块库",
        "02_资产中心\03_对标账号库",
        "02_资产中心\04_爆款选题库",
        "02_资产中心\05_爆款开头库",
        "02_资产中心\06_生成正文库",
        "02_资产中心\07_润色成稿库"
    )

    foreach ($relativeDir in $assetDirs) {
        $fullDir = Join-Path $rootPath $relativeDir
        if (-not (Test-Path -LiteralPath $fullDir)) {
            continue
        }

        $files = Get-ChildItem -LiteralPath $fullDir -File -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($file in $files) {
            if (-not (Test-AllowedPublicFile -File $file)) {
                Add-Violation "公开层资产目录疑似包含真实业务资产: $(Get-RelativePath $file.FullName)"
            }
        }
    }
}

function Assert-RequiredPublicTemplates {
    $required = @(
        "01_Agent系统\01_小姜-CEO助理Agent\00_小姜工作台模板.md",
        "02_资产中心\01_原始知识库\00_原始资料输入清单模板.md",
        "02_资产中心\03_对标账号库\字段模板.md",
        "02_资产中心\04_爆款选题库\README.md",
        "02_资产中心\04_爆款选题库\00_手动输入选题表模板.md",
        "02_资产中心\04_爆款选题库\样板-爆款选题分类表.md",
        "02_资产中心\05_爆款开头库\README.md",
        "02_资产中心\05_爆款开头库\00_爆款开头选中清单模板.md",
        "02_资产中心\05_爆款开头库\样板-爆款开头拆解.md",
        "02_资产中心\06_生成正文库\README.md",
        "02_资产中心\06_生成正文库\样板-干货型生成正文.md",
        "02_资产中心\07_润色成稿库\README.md",
        "02_资产中心\07_润色成稿库\输入说明.md",
        "02_资产中心\07_润色成稿库\字段说明.md",
        "02_资产中心\07_润色成稿库\样板-干货型成稿.md",
        "02_资产中心\02_内容模块库\99_工作纪实模块\README.md",
        "02_资产中心\02_内容模块库\99_工作纪实模块\01_金句模块\样板-工作纪实金句模块.md",
        "02_资产中心\02_内容模块库\99_工作纪实模块\02_误区模块\样板-工作纪实误区模块.md",
        "02_资产中心\02_内容模块库\99_工作纪实模块\03_步骤模块\样板-工作纪实步骤模块.md",
        "02_资产中心\02_内容模块库\99_工作纪实模块\05_模块索引\字段说明.md",
        "10_Skills武器库\书籍内容模块拆解Skill\README.md",
        "10_Skills武器库\书籍内容模块拆解Skill\输入说明.md",
        "10_Skills武器库\书籍内容模块拆解Skill\输出说明.md",
        "10_Skills武器库\书籍内容模块拆解Skill\依赖说明.md",
        "10_Skills武器库\爆款开头成稿生成Skill\README.md",
        "10_Skills武器库\爆款开头成稿生成Skill\输入说明.md",
        "10_Skills武器库\爆款开头成稿生成Skill\输出说明.md",
        "10_Skills武器库\爆款开头成稿生成Skill\依赖说明.md"
    )

    foreach ($relative in $required) {
        $full = Join-Path $rootPath $relative
        if (-not (Test-Path -LiteralPath $full)) {
            Add-Violation "公开层缺少关键模板或说明文件: $relative"
        }
    }
}

function Assert-NoLocalPathDependency {
    $scanDirs = @(
        "README.md",
        "00_系统说明",
        "01_Agent系统",
        "02_资产中心",
        "03_工作流中心",
        "10_Skills武器库",
        "tools"
    )

    $patterns = @(
        ("E:" + "\AI流量工厂\_private"),
        ("_private" + "\00_外部来料区")
    )

    $regexPatterns = @(
        (("E:" + "\\AI流量工厂\\") + "讲干货-AI流量工厂"),
        (("E:" + "\\AI流量工厂\\") + "热门播客-AI流量工厂"),
        (("E:" + "\\AI流量工厂\\") + "推荐型-AI流量工厂")
    )

    $literalPatterns = @(
        ("干货" + "对标开头拆解Skill"),
        ("播客" + "对标开头拆解Skill"),
        ("_private/assets/04_" + "对标结构库/01_开头结构"),
        ("_private/assets/04_" + "选题库"),
        ("02_资产中心/04_" + "选题库"),
        ("选中" + "开头结构"),
        ("爆款" + "开头卡片拆解")
    )

    $sensitiveFilePatterns = @(
        "BK001_姜胡说_作弊",
        "douyin.com/video/",
        "https://www.douyin.com/video/",
        "C:\Users\Administrator",
        "E:\AI流量工厂\_private"
    )

    foreach ($relative in $scanDirs) {
        $target = Join-Path $rootPath $relative
        if (-not (Test-Path -LiteralPath $target)) {
            continue
        }

        $items = Get-Item -LiteralPath $target -Force
        $files = @()
        if ($items.PSIsContainer) {
            $files = Get-ChildItem -LiteralPath $target -File -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            $files = @($items)
        }

        foreach ($file in $files) {
            if ($file.FullName -eq (Join-Path $rootPath "tools\check_public_release.ps1")) {
                continue
            }
            $allowedExtensions = @(".md", ".ps1", ".py", ".json", ".yaml", ".yml", ".txt", ".gitignore")
            if (-not $allowedExtensions.Contains($file.Extension)) {
                continue
            }

            $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($null -eq $content) {
                continue
            }
            foreach ($pattern in $patterns) {
                if ($content.Contains($pattern)) {
                    Add-Violation "公开层文件含本机或作者私有路径依赖: $(Get-RelativePath $file.FullName) -> $pattern"
                }
            }

            foreach ($regexPattern in $regexPatterns) {
                if ($content -match $regexPattern) {
                    Add-Violation "公开层文件含本机或作者旧工作区路径: $(Get-RelativePath $file.FullName) -> $regexPattern"
                }
            }

            foreach ($pattern in $literalPatterns) {
                if ($content.Contains($pattern)) {
                    Add-Violation "公开层文件仍含已退役开头链路引用: $(Get-RelativePath $file.FullName) -> $pattern"
                }
            }

            foreach ($pattern in $sensitiveFilePatterns) {
                if ($content.Contains($pattern)) {
                    Add-Violation "公开层文件疑似含真实私域或真实平台数据: $(Get-RelativePath $file.FullName) -> $pattern"
                }
            }
        }
    }
}

function Assert-NoRuntimeOutputs {
    $runtimeDirs = Get-ChildItem -LiteralPath $rootPath -Directory -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("outputs", ".tmp", "__pycache__") }

    foreach ($dir in $runtimeDirs) {
        if ($dir.FullName -like (Join-Path $rootPath ".git") + "*") {
            continue
        }
        Add-Violation "公开发布包不允许包含历史运行产物目录: $(Get-RelativePath $dir.FullName)"
    }

    $runtimeFiles = Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -eq ".pyc" }

    foreach ($file in $runtimeFiles) {
        if ($file.FullName -like (Join-Path $rootPath ".git") + "*") {
            continue
        }
        Add-Violation "公开发布包不允许包含历史运行产物文件: $(Get-RelativePath $file.FullName)"
    }
}

function Assert-NoPublicAuditRecords {
    $auditDir = Join-Path $rootPath "01_Agent系统\02_小审-质量审核Agent\审核记录"
    if (-not (Test-Path -LiteralPath $auditDir)) {
        return
    }

    $records = Get-ChildItem -LiteralPath $auditDir -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "正式资产前置审核单模板.md" }

    foreach ($file in $records) {
        Add-Violation "公开层不允许保留真实审核记录: $(Get-RelativePath $file.FullName)"
    }
}

if ($PackageMode) {
    Assert-NoForbiddenTopLevel
    Assert-PublicAssetDirectoriesClean
}

Assert-RequiredPublicTemplates
Assert-NoLocalPathDependency
Assert-NoRuntimeOutputs
Assert-NoPublicAuditRecords

if ($violations.Count -gt 0) {
    Write-Host ""
    Write-Host "发现需要处理的公开发布风险:"
    foreach ($item in $violations) {
        Write-Host "- $item"
    }
    exit 1
}

if ($PackageMode) {
    Write-Host "公开发布包检查通过。"
} else {
    Write-Host "本地公开层检查通过。"
}

