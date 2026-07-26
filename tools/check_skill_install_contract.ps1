$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Join-Path (Split-Path -Parent $PSScriptRoot) "10_Skills武器库"
$skillDirs = Get-ChildItem -LiteralPath $root -Directory | Sort-Object Name

$requiredNow = @("SKILL.md", "migration.json")
$requiredBeforeRelease = @("README.md", "输入说明.md", "输出说明.md", "依赖说明.md", "公开状态.md")

$missingNow = New-Object System.Collections.Generic.List[string]
$missingRelease = New-Object System.Collections.Generic.List[string]

foreach ($dir in $skillDirs) {
    foreach ($name in $requiredNow) {
        $path = Join-Path $dir.FullName $name
        if (-not (Test-Path -LiteralPath $path)) {
            $missingNow.Add("$($dir.Name): 缺少当前最低文件 $name") | Out-Null
        }
    }
    foreach ($name in $requiredBeforeRelease) {
        $path = Join-Path $dir.FullName $name
        if (-not (Test-Path -LiteralPath $path)) {
            $missingRelease.Add("$($dir.Name): 缺少首发前文件 $name") | Out-Null
        }
    }
}

if ($missingNow.Count -gt 0) {
    Write-Host "当前最低安装契约未满足："
    $missingNow | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host "当前最低安装契约通过。"

if ($missingRelease.Count -gt 0) {
    Write-Host ""
    Write-Host "注意：以下文件仍需在首次正式发布前补齐："
    $missingRelease | ForEach-Object { Write-Host "- $_" }
}
