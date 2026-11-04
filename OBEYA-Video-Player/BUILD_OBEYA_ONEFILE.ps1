# Build OBEYA.exe with only the .NET Framework compiler included with Windows 10/11.
# Place the ORIGINAL OBEYA.mp4 and ORIGINAL icon PNG beside this script.
# The finished EXE holds the whole video and does NOT extract it when launched.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$searchFolders = @(
 $root,
 (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'),
 ([Environment]::GetFolderPath('DesktopDirectory')),
 ([Environment]::GetFolderPath('MyVideos')),
 ([Environment]::GetFolderPath('MyDocuments'))
) | Select-Object -Unique
$video = $null
foreach ($folder in $searchFolders) {
 if (!(Test-Path -LiteralPath $folder -PathType Container)) { continue }
 $candidates = @(Get-ChildItem -LiteralPath $folder -File -ErrorAction SilentlyContinue |
   Where-Object { $_.Name -match '^OBEYA(?:\s*\(\d+\))?\.mp4
$html = Join-Path $root 'OBEYA.html'
$source = Join-Path $root 'OBEYA_ONEFILE_Launcher.cs'
$ico = Join-Path $root 'OBEYA.ico'
$exe = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'OBEYA.exe'
$stub = Join-Path $root 'OBEYA_runner.exe'

if (!$video -or !(Test-Path -LiteralPath $video)) { throw 'Cannot locate OBEYA.mp4. Download your original OBEYA.mp4 to the Windows Downloads folder and try again.' }
if (!(Test-Path -LiteralPath $html)) { throw 'Missing OBEYA.html.' }
if (!(Test-Path -LiteralPath $source)) { throw 'Missing OBEYA_Launcher.cs.' }

$iconNames = @(
 'Cinematic OBEYA Play Icon(2).png',
 'Cinematic OBEYA Play Icon(1).png',
 'Cinematic OBEYA Play Icon.png',
 'OBEYA_ICON.png',
 'OBEYA.png',
 'icon.png'
)
$iconSource = $null
foreach ($folder in $searchFolders) {
 if (!(Test-Path -LiteralPath $folder -PathType Container)) { continue }
 foreach ($item in $iconNames) {
   $candidate = Join-Path $folder $item
   if (Test-Path -LiteralPath $candidate) { $iconSource = $candidate; break }
 }
 if ($iconSource) { break }
}
if (!$iconSource) { throw 'Original OBEYA icon PNG not found. Save your original icon next to this script as OBEYA.png.' }

Add-Type -AssemblyName System.Drawing

function Make-Icon {
  param([string]$ImageFile, [string]$OutFile)
  $img = [System.Drawing.Image]::FromFile($ImageFile)
  $sizes = @(16, 24, 32, 48, 64, 128, 256)
  $entries = New-Object 'System.Collections.Generic.List[byte[]]'
  try {
    foreach ($side in $sizes) {
      $bmp = [System.Drawing.Bitmap]::new($side, $side, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
      $gfx = [System.Drawing.Graphics]::FromImage($bmp)
      try {
        $gfx.Clear([System.Drawing.Color]::Transparent)
        $gfx.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $scale = [Math]::Min($side / [double]$img.Width, $side / [double]$img.Height)
        $w = [int][Math]::Round($img.Width * $scale)
        $h = [int][Math]::Round($img.Height * $scale)
        $gfx.DrawImage($img, [int](($side-$w)/2), [int](($side-$h)/2), $w, $h)
      } finally { $gfx.Dispose() }

      $ms = New-Object System.IO.MemoryStream
      $writer = New-Object System.IO.BinaryWriter($ms)
      try {
        $stride = [int]([Math]::Ceiling($side/32.0)*4)
        $pixelBytes = $side*$side*4
        $maskBytes = $side*$stride
        # Standard 32-bit uncompressed DIB ICO: compatible with old and new csc.exe.
        $writer.Write([UInt32]40)
        $writer.Write([Int32]$side)
        $writer.Write([Int32]($side*2))
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]0)
        $writer.Write([UInt32]$pixelBytes)
        $writer.Write([Int32]0)
        $writer.Write([Int32]0)
        $writer.Write([UInt32]0)
        $writer.Write([UInt32]0)
        for ($y=$side-1; $y -ge 0; $y--) {
          for ($x=0; $x -lt $side; $x++) {
            $c = $bmp.GetPixel($x,$y)
            $writer.Write([byte]$c.B)
            $writer.Write([byte]$c.G)
            $writer.Write([byte]$c.R)
            $writer.Write([byte]$c.A)
          }
        }
        for ($y=$side-1; $y -ge 0; $y--) {
          $row = New-Object 'byte[]' $stride
          for ($x=0; $x -lt $side; $x++) {
            $alpha = $bmp.GetPixel($x,$y).A
            if ($alpha -lt 20) {
              $ix = [int][Math]::Floor($x/8)
              $row[$ix] = [byte]($row[$ix] -bor (0x80 -shr ($x%8)))
            }
          }
          $writer.Write($row)
        }
        $writer.Flush()
        $entries.Add($ms.ToArray())
      } finally {
        $writer.Dispose()
        $ms.Dispose()
        $bmp.Dispose()
      }
    }

    $file = [System.IO.File]::Open($OutFile,[System.IO.FileMode]::Create,[System.IO.FileAccess]::Write)
    $output = New-Object System.IO.BinaryWriter($file)
    try {
      $output.Write([UInt16]0)
      $output.Write([UInt16]1)
      $output.Write([UInt16]$sizes.Count)
      $offset = 6 + (16*$sizes.Count)
      for ($i=0; $i -lt $sizes.Count; $i++) {
        $s = $sizes[$i]
        $output.Write([byte]($(if ($s -eq 256) {0} else {$s})))
        $output.Write([byte]($(if ($s -eq 256) {0} else {$s})))
        $output.Write([byte]0)
        $output.Write([byte]0)
        $output.Write([UInt16]1)
        $output.Write([UInt16]32)
        $output.Write([UInt32]$entries[$i].Length)
        $output.Write([UInt32]$offset)
        $offset += $entries[$i].Length
      }
      foreach ($bytes in $entries) { $output.Write($bytes) }
    } finally { $output.Dispose() }
  } finally { $img.Dispose() }
}

Write-Host 'OBEYA Video Player -- Windows single-EXE build' -ForegroundColor Cyan
Write-Host ('Original video: {0:N1} MB' -f ((Get-Item -LiteralPath $video).Length/1MB))
Write-Host 'Creating Windows ICO from supplied original character image...'
Make-Icon -ImageFile $iconSource -OutFile $ico

$frameworkDirs = @(
 (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
 (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$csc = $frameworkDirs | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$csc) { throw 'The built-in .NET Framework 4.x C# compiler was not found on this Windows installation.' }

Write-Host 'Compiling the small launcher with HTML and icon only...'
# Compiles only the tiny launcher, HTML, and the original icon.
# Large MP4 bytes are appended unchanged AFTER compilation as a PE overlay.
$argsLine = '/nologo /target:winexe /platform:anycpu /optimize+ /reference:System.Windows.Forms.dll /win32icon:"{0}" /resource:"{1}",ObeyaHTML /resource:"{2}",ObeyaIcon /out:"{3}" "{4}"' -f $ico,$html,$ico,$stub,$source
$process = Start-Process -FilePath $csc -ArgumentList $argsLine -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) { throw ('Compiler failed: exit code ' + $process.ExitCode) }
if (!(Test-Path -LiteralPath $stub)) { throw 'The Windows launcher did not compile.' }

Write-Host 'Copying launcher to the Desktop and appending your ORIGINAL MP4...' -ForegroundColor Cyan
[System.IO.File]::Copy($stub,$exe,$true)
$videoBytes = (Get-Item -LiteralPath $video).Length
$destination = [System.IO.FileStream]::new($exe,[System.IO.FileMode]::Append,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
$sourceVideo = [System.IO.FileStream]::new($video,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
$offset = $destination.Position
try {
  $buffer = New-Object 'byte[]' 1048576
  while (($read = $sourceVideo.Read($buffer,0,$buffer.Length)) -gt 0) {
    $destination.Write($buffer,0,$read)
  }
  $writer = [System.IO.BinaryWriter]::new($destination,[System.Text.Encoding]::ASCII,$true)
  try {
    $writer.Write([System.Text.Encoding]::ASCII.GetBytes('OBEYAV01'))
    $writer.Write([Int64]$offset)
    $writer.Write([Int64]$videoBytes)
    $writer.Flush()
  } finally { $writer.Dispose() }
  $destination.Flush()
} finally { $sourceVideo.Dispose(); $destination.Dispose() }

$exeBytes = (Get-Item -LiteralPath $exe).Length
if ($exeBytes -ne ($offset + $videoBytes + 24)) {
 throw 'FAIL: OBEYA.exe does not contain the complete original MP4.'
}
# Validate the exact trailer used by the launcher. This does not edit media.
$verify = [System.IO.FileStream]::new($exe,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
try {
  $verify.Seek(-24,[System.IO.SeekOrigin]::End) | Out-Null
  $reader = [System.IO.BinaryReader]::new($verify,[System.Text.Encoding]::ASCII,$true)
  try {
    $foundMarker = [System.Text.Encoding]::ASCII.GetString($reader.ReadBytes(8))
    $foundOffset = $reader.ReadInt64()
    $foundLength = $reader.ReadInt64()
    if ($foundMarker -ne 'OBEYAV01' -or $foundOffset -ne $offset -or $foundLength -ne $videoBytes) {
      throw 'FAIL: the embedded video trailer could not be validated.'
    }
  } finally { $reader.Dispose() }
} finally { $verify.Dispose() }
Remove-Item -LiteralPath $stub -Force -ErrorAction SilentlyContinue
Write-Host ''
Write-Host 'SUCCESS: The complete OBEYA.exe is on the Desktop.' -ForegroundColor Green
Write-Host ('Size: {0:N1} MB' -f ($exeBytes / 1MB))
Write-Host 'Your entire unmodified MP4, HTML controls and original icon are in this ONE EXE.'
Write-Host 'The only runtime dependency is Microsoft Edge or Google Chrome already installed on Windows.'
Write-Host 'Launching OBEYA.exe now...' -ForegroundColor Cyan
Start-Process -FilePath $exe
