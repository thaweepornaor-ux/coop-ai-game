# OBEYA Video Player - one-time Desktop installation for Windows 10/11.
# After setup, the app icon opens the original MP4 OFFLINE.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Add-Type -AssemblyName System.Drawing
  $myFolder = Split-Path -Parent $MyInvocation.MyCommand.Path
  $profileFolder = [Environment]::GetFolderPath('UserProfile')
  $downloadFolder = Join-Path $profileFolder 'Downloads'
  $desktop = [Environment]::GetFolderPath('DesktopDirectory')
  $searchFolders = @($myFolder, $downloadFolder, $desktop) | Select-Object -Unique
  function Find-OriginalFile {
    param([string]$Kind)
    foreach ($dir in $searchFolders) {
      if (!(Test-Path -LiteralPath $dir -PathType Container)) { continue }
      $hits = @()
      foreach ($file in (Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue)) {
        if ($Kind -eq 'video' -and $file.Name -match '^OBEYA(?:\s*\(\d+\))?\.mp4$' -and $file.Length -gt 1048576) { $hits += $file }
        if ($Kind -eq 'icon' -and ($file.Name -match '^Cinematic OBEYA Play Icon(?:\s*\(\d+\))?\.png$' -or $file.Name -match '^OBEYA(?:_ICON)?(?:\s*\(\d+\))?\.png$')) { $hits += $file }
      }
      if ($hits.Count -gt 0) { return $hits | Sort-Object LastWriteTime -Descending | Select-Object -First 1 }
    }
    return $null
  }
  $video = Find-OriginalFile 'video'
  $image = Find-OriginalFile 'icon'
  if (!$video) { throw 'OBEYA.mp4 is missing. Download OBEYA.mp4 from ChatGPT to your Downloads folder and rerun setup.' }
  if (!$image) { throw 'OBEYA icon PNG is missing. Download Cinematic OBEYA Play Icon.png from ChatGPT to Downloads and rerun setup.' }

  $app = Join-Path $env:LOCALAPPDATA 'OBEYA Video Player'
  if (!(Test-Path -LiteralPath $app)) { New-Item -Path $app -ItemType Directory | Out-Null }
  $mp4Target = Join-Path $app 'OBEYA.mp4'
  $pngTarget = Join-Path $app 'OBEYA.png'
  $htmlTarget = Join-Path $app 'OBEYA.html'
  $icoTarget = Join-Path $app 'OBEYA.ico'
  Write-Host ('Video: ' + $video.FullName)
  Write-Host ('Icon : ' + $image.FullName)
  Write-Host ('MP4  : {0:N1} MB' -f ($video.Length / 1MB))
  Write-Host 'Copying the original video into the application folder...'
  if ($video.FullName -ine $mp4Target) { Copy-Item -LiteralPath $video.FullName -Destination $mp4Target -Force }
  if ($image.FullName -ine $pngTarget) { Copy-Item -LiteralPath $image.FullName -Destination $pngTarget -Force }
  if ((Get-Item -LiteralPath $mp4Target).Length -ne $video.Length) { throw 'Video copy verification failed.' }

  Write-Host 'Installing offline HTML player...'
  $url = 'https://raw.githubusercontent.com/thaweepornaor-ux/coop-ai-game/obeya-player-build-kit/OBEYA-Video-Player/OBEYA.html'
  Invoke-WebRequest -Uri $url -OutFile $htmlTarget -UseBasicParsing
  $htmlText = [System.IO.File]::ReadAllText($htmlTarget)
  if ($htmlText.Length -lt 5000 -or !$htmlText.Contains('id="stage"') -or !$htmlText.Contains('OBEYA.mp4')) {
    throw 'The HTML video player download did not pass verification.'
  }

  Write-Host 'Creating Windows icon from the original PNG...'
  $img = [System.Drawing.Image]::FromFile($pngTarget)
  $bmp = [System.Drawing.Bitmap]::new(256, 256)
  $graphics = [System.Drawing.Graphics]::FromImage($bmp)
  try {
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $scale = [Math]::Min(256.0 / $img.Width, 256.0 / $img.Height)
    $w = [int][Math]::Round($img.Width * $scale)
    $h = [int][Math]::Round($img.Height * $scale)
    $graphics.DrawImage($img, [int]((256-$w)/2), [int]((256-$h)/2), $w, $h)
    $memory = [System.IO.MemoryStream]::new()
    try {
      $bmp.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
      $bytes = $memory.ToArray()
    } finally { $memory.Dispose() }
    $fileStream = [System.IO.File]::Open($icoTarget, [System.IO.FileMode]::Create)
    $writer = [System.IO.BinaryWriter]::new($fileStream)
    try {
      $writer.Write([UInt16]0); $writer.Write([UInt16]1); $writer.Write([UInt16]1)
      $writer.Write([byte]0); $writer.Write([byte]0)
      $writer.Write([byte]0); $writer.Write([byte]0)
      $writer.Write([UInt16]1); $writer.Write([UInt16]32)
      $writer.Write([UInt32]$bytes.Length); $writer.Write([UInt32]22)
      $writer.Write($bytes); $writer.Flush()
    } finally { $writer.Dispose() }
  } finally { $graphics.Dispose(); $bmp.Dispose(); $img.Dispose() }

  $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
  $locations = @()
  foreach ($prefix in @($pf86, $env:ProgramFiles, $env:LOCALAPPDATA)) {
    if (!$prefix) { continue }
    $locations += (Join-Path $prefix 'Microsoft\Edge\Application\msedge.exe')
    $locations += (Join-Path $prefix 'Google\Chrome\Application\chrome.exe')
  }
  $browser = $locations | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
  if (!$browser) {
    foreach ($name in @('msedge.exe','chrome.exe')) {
      $cmd = Get-Command $name -ErrorAction SilentlyContinue
      if ($cmd) { $browser = $cmd.Source; break }
    }
  }
  if (!$browser) { throw 'Microsoft Edge or Google Chrome could not be found.' }

  $fileUrl = (New-Object System.Uri($htmlTarget)).AbsoluteUri
  $arguments = '--app="' + $fileUrl + '" --new-window'
  $shortcutPath = Join-Path $desktop 'OBEYA Video Player.lnk'
  Write-Host 'Creating the OBEYA Desktop shortcut...'
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = $browser
  $shortcut.Arguments = $arguments
  $shortcut.WorkingDirectory = $app
  $shortcut.IconLocation = $icoTarget + ',0'
  $shortcut.Description = 'OBEYA Video Player - offline presentation'
  $shortcut.Save()
  if (!(Test-Path -LiteralPath $shortcutPath)) { throw 'Desktop shortcut creation failed.' }

  Write-Host 'SUCCESS: Desktop OBEYA Video Player is ready.' -ForegroundColor Green
  Write-Host ('Shortcut: ' + $shortcutPath)
  Write-Host 'From now on, double-click the Desktop icon. Internet is NOT needed.'
  Write-Host 'Opening OBEYA now...'
  Start-Process -FilePath $browser -ArgumentList $arguments -WorkingDirectory $app
  exit 0
} catch {
  Write-Host ''
  Write-Host 'SETUP ERROR:' -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  exit 1
}
