param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Arch = "x64",
    [string]$Commit = "dev",
    [string]$BuildDate = "",
    [string]$ProjectUrl = "https://github.com/ecotranscribe/ecotranscribe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$AppDir = Join-Path $Dist "EcoTranscribe Desktop"
if (-not (Test-Path $AppDir)) {
    throw "Application introuvable : $AppDir"
}

$notice = Join-Path $AppDir "LIRE-MOI-Windows.txt"
& uv run --project $Root python (Join-Path $Root "packaging\render_notices.py") `
    --os windows --output $notice --version $Version --arch $Arch `
    --commit $Commit --build-date $BuildDate --project-url $ProjectUrl
if ($LASTEXITCODE -ne 0) {
    throw "Rendu de la notice impossible"
}

Copy-Item (Join-Path $Root "LICENSE") $AppDir
Copy-Item (Join-Path $Root "THIRD_PARTY_NOTICES.md") $AppDir
Copy-Item (Join-Path $Root "packaging\notices") $AppDir -Recurse -Force

$Zip = Join-Path $Dist "ecotranscribe-desktop-lite-windows-$Arch-$Version.zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path $AppDir -DestinationPath $Zip -CompressionLevel Optimal

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($Zip)
try {
    $names = @($archive.Entries | ForEach-Object { $_.FullName -replace '\\', '/' })
    foreach ($required in @(
        "EcoTranscribe Desktop/EcoTranscribe Desktop.exe",
        "EcoTranscribe Desktop/_internal/bin/ffmpeg.exe",
        "EcoTranscribe Desktop/_internal/bin/ffprobe.exe",
        "EcoTranscribe Desktop/LIRE-MOI-Windows.txt",
        "EcoTranscribe Desktop/LICENSE",
        "EcoTranscribe Desktop/THIRD_PARTY_NOTICES.md"
    )) {
        if (-not ($names -contains $required)) {
            throw "Entrée absente du ZIP : $required"
        }
    }
    if (-not ($names | Where-Object { $_ -like "EcoTranscribe Desktop/_internal/*" })) {
        throw "Dossier _internal absent du ZIP"
    }
}
finally {
    $archive.Dispose()
}

$Setup = Join-Path $Dist "ecotranscribe-desktop-lite-windows-$Arch-$Version-setup.exe"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DMyAppVersion=$Version" "/DMyAppArch=$Arch" `
        (Join-Path $Root "packaging\windows.iss")
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Inno Setup a échoué : installeur optionnel ignoré."
        $Setup = $null
    }
}
else {
    Write-Warning "Inno Setup absent : installeur optionnel non produit."
    $Setup = $null
}

$files = @($Zip)
if ($Setup -and (Test-Path $Setup)) {
    $files += $Setup
}
$lines = foreach ($file in $files) {
    $hash = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
    "$hash  $(Split-Path $file -Leaf)"
}
$lines | Set-Content -Encoding ASCII (Join-Path $Dist "SHA256SUMS-windows-$Arch.txt")

Write-Output "Artefacts :"
$files | ForEach-Object { Write-Output "  $_" }
