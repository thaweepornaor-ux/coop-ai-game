@echo off
setlocal
title OBEYA - Install Desktop Icon
set "OBEYA_SETUP_SELF=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:OBEYA_SETUP_SELF); $mark='__OBEYA_PS_START__'; $i=$s.LastIndexOf($mark); if($i -lt 0){throw 'Missing installer data'}; Invoke-Expression ($s.Substring($i+$mark.Length))"
if errorlevel 1 (
  echo.
  echo OBEYA setup could not finish. Read the message above.
  pause
  exit /b 1
)
echo.
echo OBEYA Desktop icon was created. Open it anytime.
pause
exit /b 0
__OBEYA_PS_START__
$ErrorActionPreference='Stop'
try {
  Add-Type -AssemblyName System.Drawing
  $homeFolder=[Environment]::GetFolderPath('UserProfile')
  $desktop=[Environment]::GetFolderPath('DesktopDirectory')
  $downloads=Join-Path $homeFolder 'Downloads'
  $here=Split-Path -Parent $env:OBEYA_SETUP_SELF
  $folders=@($here,$downloads,$desktop) | Select-Object -Unique
  function FindOBEYA([string]$kind) {
    foreach($dir in $folders) {
      if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
      $items=Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue
      foreach($f in ($items | Sort-Object LastWriteTime -Descending)){
        if($kind -eq 'video' -and $f.Name -match '^OBEYA(?:\s*\(\d+\))?\.mp4$' -and $f.Length -gt 1048576){return $f}
        if($kind -eq 'image' -and ($f.Name -match '^OBEYA(?:_ICON)?(?:\s*\(\d+\))?\.png$' -or $f.Name -match '^Cinematic OBEYA Play Icon(?:\s*\(\d+\))?\.png$')){return $f}
        if($kind -eq 'html' -and $f.Name -match '^OBEYA_(?:READY_OFFLINE|PLAYER_CUSTOM_ICON)(?:\s*\(\d+\))?\.html$'){return $f}
      }
    }
    return $null
  }
  $mp4=FindOBEYA 'video'
  $png=FindOBEYA 'image'
  $html=FindOBEYA 'html'
  if(!$mp4){throw 'OBEYA.mp4 was not found. Put the video in Downloads, then run this file again.'}
  if(!$png){throw 'OBEYA(1).png was not found. Save the OBEYA woman icon to Downloads, then run this file again.'}
  $app=Join-Path $env:LOCALAPPDATA 'OBEYA Video Player'
  if(!(Test-Path -LiteralPath $app)){New-Item -Path $app -ItemType Directory | Out-Null}
  $destVideo=Join-Path $app 'OBEYA.mp4'
  $destPng=Join-Path $app 'OBEYA.png'
  $destHtml=Join-Path $app 'OBEYA.html'
  $destIco=Join-Path $app 'OBEYA.ico'
  Write-Host 'Installing OBEYA in your Windows profile...' -ForegroundColor Cyan
  Write-Host ('Video: '+$mp4.FullName)
  Write-Host ('Icon: '+$png.FullName)
  if($mp4.FullName -ine $destVideo){Copy-Item -LiteralPath $mp4.FullName -Destination $destVideo -Force}
  if($png.FullName -ine $destPng){Copy-Item -LiteralPath $png.FullName -Destination $destPng -Force}
  if((Get-Item -LiteralPath $destVideo).Length -ne $mp4.Length){throw 'Video copy failed.'}
  if($html){
    Copy-Item -LiteralPath $html.FullName -Destination $destHtml -Force
  } else {
    $uri='https://raw.githubusercontent.com/thaweepornaor-ux/coop-ai-game/obeya-player-build-kit/OBEYA-Video-Player/OBEYA_READY_OFFLINE.html'
    Write-Host 'Getting the HTML player (internet needed only for this first setup)...'
    Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $destHtml
  }
  $src=[IO.File]::ReadAllText($destHtml)
  if($src.Length -lt 8000 -or !$src.Contains('id="video"') -or !$src.Contains('id="start"')){throw 'OBEYA HTML verification failed.'}
  # Keep the exact OBEYA artwork; resize only for the Windows icon container.
  $image=[System.Drawing.Image]::FromFile($destPng)
  $bitmap=New-Object System.Drawing.Bitmap -ArgumentList 256,256
  $g=[System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $g.Clear([System.Drawing.Color]::Transparent)
    $g.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $scale=[Math]::Min(256.0/$image.Width,256.0/$image.Height)
    $w=[int][Math]::Round($image.Width*$scale)
    $h=[int][Math]::Round($image.Height*$scale)
    $g.DrawImage($image,[int]((256-$w)/2),[int]((256-$h)/2),$w,$h)
    $ms=New-Object System.IO.MemoryStream
    try { $bitmap.Save($ms,[System.Drawing.Imaging.ImageFormat]::Png); $bytes=$ms.ToArray() }
    finally { $ms.Dispose() }
    $fs=[IO.File]::Create($destIco)
    $bw=New-Object System.IO.BinaryWriter($fs)
    try {
      $bw.Write([UInt16]0);$bw.Write([UInt16]1);$bw.Write([UInt16]1)
      $bw.Write([byte]0);$bw.Write([byte]0);$bw.Write([byte]0);$bw.Write([byte]0)
      $bw.Write([UInt16]1);$bw.Write([UInt16]32)
      $bw.Write([UInt32]$bytes.Length);$bw.Write([UInt32]22)
      $bw.Write($bytes);$bw.Flush()
    } finally {$bw.Dispose()}
  } finally {$g.Dispose();$bitmap.Dispose();$image.Dispose()}
  $pf86=[Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
  $browsers=@()
  foreach($dir in @($pf86,$env:ProgramFiles,$env:LOCALAPPDATA)){
    if($dir){
      $browsers+=Join-Path $dir 'Microsoft\Edge\Application\msedge.exe'
      $browsers+=Join-Path $dir 'Google\Chrome\Application\chrome.exe'
    }
  }
  $browser=$browsers | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf} | Select-Object -First 1
  if(!$browser){throw 'Microsoft Edge or Google Chrome not found.'}
  $url=([System.Uri]$destHtml).AbsoluteUri
  $arguments='--app="'+$url+'" --new-window'
  $lnk=Join-Path $desktop 'OBEYA Video Player.lnk'
  $shell=New-Object -ComObject WScript.Shell
  $shortcut=$shell.CreateShortcut($lnk)
  $shortcut.TargetPath=$browser
  $shortcut.Arguments=$arguments
  $shortcut.IconLocation=$destIco+',0'
  $shortcut.WorkingDirectory=$app
  $shortcut.Description='OBEYA Video Player - Offline'
  $shortcut.Save()
  if(!(Test-Path -LiteralPath $lnk)){throw 'The Desktop shortcut could not be created.'}
  Write-Host 'SUCCESS: OBEYA Desktop icon created.' -ForegroundColor Green
  Write-Host 'Double-click the new icon for offline playback.'
  Start-Process -FilePath $browser -ArgumentList $arguments -WorkingDirectory $app
  exit 0
} catch {
  Write-Host ('SETUP ERROR: '+$_.Exception.Message) -ForegroundColor Red
  exit 1
}
