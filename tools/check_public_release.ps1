param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$PackageMode,
    [switch]$AllowGitMetadata
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$violations = New-Object System.Collections.Generic.List[string]

$hiddenRelativeDirs = @(
    "02_资产中心\01_原始知识库\99_我的工作纪实",
    "02_资产中心\02_内容模块库\99_工作纪实模块",
    "01_Agent系统\01_小姜-CEO助理Agent\99_本地运行记录",
    "01_Agent系统\02_小审-质量审核Agent\99_审核记录",
    "01_Agent系统\03_小息-信息采集Agent\99_执行记录",
    "01_Agent系统\04_小拆-内容拆解Agent\99_执行记录",
    "03_工作流中心\01_短视频主工作流\99_运行记录"
)

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

function Assert-HiddenDirsExcluded {
    foreach ($relative in $hiddenRelativeDirs) {
        $full = Join-Path $rootPath $relative
        if (Test-Path -LiteralPath $full) {
            Add-Violation "公开发布包不允许包含本地隐藏目录: $relative"
        }
    }
}

function Assert-RequiredMainChain {
    $required = @(
        "AGENTS.md",
        "README.md",
        "00_系统说明",
        "01_Agent系统",
        "02_资产中心",
        "03_工作流中心",
        "10_Skills武器库",
        "tools",
        "02_资产中心\01_原始知识库",
        "02_资产中心\02_内容模块库",
        "02_资产中心\03_对标账号库",
        "02_资产中心\04_爆款选题库",
        "02_资产中心\05_爆款开头库",
        "02_资产中心\06_生成正文库",
        "02_资产中心\07_润色成稿库"
    )

    foreach ($relative in $required) {
        $full = Join-Path $rootPath $relative
        if (-not (Test-Path -LiteralPath $full)) {
            Add-Violation "正式主链缺失: $relative"
        }
    }
}

function Assert-NoRetiredMainChainDocs {
    $scanDirs = @(
        "README.md",
        "AGENTS.md",
        "00_系统说明",
        "01_Agent系统",
        "02_资产中心",
        "03_工作流中心",
        "10_Skills武器库",
        "tools"
    )

    $literalPatterns = @(
        "_private/assets",
        "_private/agent_records",
        "_private/workflow_records",
        "_private/tools",
        "公开层只保留结构和样板",
        "私域作为真实工作库",
        "爆款开头卡片拆解",
        "选中开头结构"
    )

    $regexPatterns = @(
        "02_资产中心[/\\]04_选题库",
        "02_资产中心[/\\]04_对标结构库",
        "02_资产中心[/\\]06_视觉库",
        "02_资产中心[/\\]07_复盘库",
        "E:\\AI流量工厂\\_private",
        "C:\\Users\\Administrator"
    )

    $hiddenFullPrefixes = $hiddenRelativeDirs | ForEach-Object { [System.IO.Path]::GetFullPath((Join-Path $rootPath $_)) }
    $skipFiles = @(
        (Join-Path $rootPath "tools\check_public_release.ps1"),
        (Join-Path $rootPath "tools\prepare_public_release.ps1"),
        (Join-Path $rootPath "tools\sync_public_templates.py")
    ) | ForEach-Object { [System.IO.Path]::GetFullPath($_) }

    foreach ($relative in $scanDirs) {
        $target = Join-Path $rootPath $relative
        if (-not (Test-Path -LiteralPath $target)) {
            continue
        }

        $item = Get-Item -LiteralPath $target -Force
        $files = @()
        if ($item.PSIsContainer) {
            $files = Get-ChildItem -LiteralPath $target -File -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            $files = @($item)
        }

        foreach ($file in $files) {
            $fullName = [System.IO.Path]::GetFullPath($file.FullName)
            if ($skipFiles -contains $fullName) {
                continue
            }
            if ($hiddenFullPrefixes | Where-Object { $fullName.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase) }) {
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

            foreach ($pattern in $literalPatterns) {
                if ($content.Contains($pattern)) {
                    Add-Violation "现役文档或脚本仍含旧双轨/退役口径: $(Get-RelativePath $file.FullName) -> $pattern"
                }
            }

            foreach ($pattern in $regexPatterns) {
                if ($content -match $pattern) {
                    Add-Violation "现役文档或脚本仍含退役路径或作者本机绝对路径: $(Get-RelativePath $file.FullName) -> $pattern"
                }
            }
        }
    }
}

function Assert-NoRuntimeOutputs {
    $runtimeDirs = Get-ChildItem -LiteralPath $rootPath -Directory -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("outputs", ".tmp", "__pycache__") }

    foreach ($dir in $runtimeDirs) {
        if ($AllowGitMetadata -and $dir.FullName -like (Join-Path $rootPath ".git") + "*") {
            continue
        }
        Add-Violation "公开发布包不允许包含运行产物目录: $(Get-RelativePath $dir.FullName)"
    }

    $runtimeFiles = Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".pyc", ".pyo") }

    foreach ($file in $runtimeFiles) {
        if ($AllowGitMetadata -and $file.FullName -like (Join-Path $rootPath ".git") + "*") {
            continue
        }
        Add-Violation "公开发布包不允许包含运行产物文件: $(Get-RelativePath $file.FullName)"
    }
}

Assert-RequiredMainChain

if ($PackageMode) {
    Assert-NoForbiddenTopLevel
    Assert-HiddenDirsExcluded
}

Assert-NoRetiredMainChainDocs
Assert-NoRuntimeOutputs

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
    Write-Host "本地主链检查通过。"
}
