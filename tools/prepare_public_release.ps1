param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutDir = "E:\AI流量工厂-public",
    [string]$TempDir = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "tmp\public-release\AI流量工厂-public")
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$tempPath = [System.IO.Path]::GetFullPath($TempDir)
$outPath = [System.IO.Path]::GetFullPath($OutDir)

function Assert-SafeOutputPath {
    param([string]$PathToCheck)

    $forbiddenTargets = @(
        (Join-Path $rootPath "_private"),
        (Join-Path $rootPath "讲干货-AI流量工厂"),
        (Join-Path $rootPath "热门播客-AI流量工厂"),
        (Join-Path $rootPath "推荐型-AI流量工厂"),
        (Join-Path $rootPath ".git"),
        (Join-Path $rootPath ".agents"),
        (Join-Path $rootPath ".codex"),
        (Join-Path $rootPath ".obsidian")
    )

    $resolvedOut = [System.IO.Path]::GetFullPath($PathToCheck)
    foreach ($forbidden in $forbiddenTargets) {
        $resolvedForbidden = [System.IO.Path]::GetFullPath($forbidden)
        if ($resolvedOut.StartsWith($resolvedForbidden, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "输出目录不能位于私有层、历史工作区或系统目录内: $PathToCheck"
        }
    }
}

function Copy-PublicItem {
    param(
        [string]$RelativePath,
        [string]$DestinationRoot
    )

    $source = Join-Path $rootPath $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        return
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    $parent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $item = Get-Item -LiteralPath $source -Force
    if ($item.PSIsContainer) {
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    } else {
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Remove-RuntimeArtifacts {
    param([string]$TargetRoot)

    if (-not (Test-Path -LiteralPath $TargetRoot)) {
        return
    }

    $runtimeDirs = Get-ChildItem -LiteralPath $TargetRoot -Directory -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("outputs", ".tmp", "__pycache__") }

    foreach ($dir in $runtimeDirs) {
        Remove-Item -LiteralPath $dir.FullName -Recurse -Force
    }

    $pycFiles = Get-ChildItem -LiteralPath $TargetRoot -File -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -eq ".pyc" }

    foreach ($file in $pycFiles) {
        Remove-Item -LiteralPath $file.FullName -Force
    }
}

function Clear-PublicRepoKeepingGit {
    param([string]$RepoPath)

    if (-not (Test-Path -LiteralPath $RepoPath)) {
        New-Item -ItemType Directory -Path $RepoPath -Force | Out-Null
        return
    }

    $items = Get-ChildItem -LiteralPath $RepoPath -Force
    foreach ($item in $items) {
        if ($item.Name -eq ".git") {
            continue
        }
        Remove-Item -LiteralPath $item.FullName -Recurse -Force
    }
}

function Copy-DirectoryContents {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $DestinationRoot -Recurse -Force
    }
}

Assert-SafeOutputPath -PathToCheck $tempPath
Assert-SafeOutputPath -PathToCheck $outPath

$syncScript = Join-Path $rootPath "tools\sync_public_templates.py"
if (Test-Path -LiteralPath $syncScript) {
    python $syncScript | Out-Host
}

if (Test-Path -LiteralPath $tempPath) {
    Remove-Item -LiteralPath $tempPath -Recurse -Force
}
New-Item -ItemType Directory -Path $tempPath -Force | Out-Null

$publicItems = @(
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    ".gitignore",
    "00_系统说明",
    "01_Agent系统",
    "02_资产中心",
    "03_工作流中心",
    "10_Skills武器库",
    "tools"
)

foreach ($relativePath in $publicItems) {
    Copy-PublicItem -RelativePath $relativePath -DestinationRoot $tempPath
}

$legacyPublicDirs = @(
    (Join-Path $tempPath "02_资产中心\06_视觉库"),
    (Join-Path $tempPath "02_资产中心\07_复盘库")
)

foreach ($legacyDir in $legacyPublicDirs) {
    if (Test-Path -LiteralPath $legacyDir) {
        Remove-Item -LiteralPath $legacyDir -Recurse -Force
    }
}

Remove-RuntimeArtifacts -TargetRoot $tempPath

$checkScript = Join-Path $tempPath "tools\check_public_release.ps1"
if (Test-Path -LiteralPath $checkScript) {
    & $checkScript -Root $tempPath -PackageMode
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Clear-PublicRepoKeepingGit -RepoPath $outPath
Copy-DirectoryContents -SourceRoot $tempPath -DestinationRoot $outPath

if (-not (Test-Path -LiteralPath (Join-Path $outPath ".git"))) {
    git -C $outPath init | Out-Host
}

$repoCheckScript = Join-Path $outPath "tools\check_public_release.ps1"
if (Test-Path -LiteralPath $repoCheckScript) {
    & $repoCheckScript -Root $outPath -PackageMode -AllowGitMetadata
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host "公开发布仓库已更新: $outPath"
Write-Host "下一步可进入公开仓库后执行: git status"
