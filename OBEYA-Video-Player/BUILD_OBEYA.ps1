# Build OBEYA.exe with only the .NET Framework compiler included with Windows 10/11.
# Place the ORIGINAL OBEYA.mp4 and ORIGINAL icon PNG beside this script.
# The finished EXE holds the whole video and does NOT extract it when launched.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$video = Join-Path $root 'OBEYA.mp4'
$html = Join-Path $root 'OBEYA.html'
$source = Join-Path $root 'OBEYA_Launcher.cs'
$ico = Join-Path $root 'OBEYA.ico'
$exe = Join-Path $root 'OBEYA.exe'

if (!(Test-Path -LiteralPath $video)) { throw 'Missing OBEYA.mp4. Use the original, unmodified video file.' }
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
foreach ($item in $iconNames) {
  $candidate = Join-Path $root $item
  if (Test-Path -LiteralPath $candidate) { $iconSource = $candidate; break }
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

Write-Host 'Embedding unmodified MP4 + HTML + ICO into OBEYA.exe (may use significant RAM)...'
$argsLine = '/nologo /target:winexe /platform:anycpu /optimize+ /reference:System.Windows.Forms.dll /win32icon:"{0}" /resource:"{1}",ObeyaVideo /resource:"{2}",ObeyaHTML /resource:"{3}",ObeyaIcon /out:"{4}" "{5}"' -f $ico,$video,$html,$ico,$exe,$source
$process = Start-Process -FilePath $csc -ArgumentList $argsLine -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) { throw ('Compiler failed: exit code ' + $process.ExitCode) }
if (!(Test-Path -LiteralPath $exe)) { throw 'Build finished but OBEYA.exe does not exist.' }

$exeBytes = (Get-Item -LiteralPath $exe).Length
$videoBytes = (Get-Item -LiteralPath $video).Length
if ($exeBytes -lt $videoBytes) { throw 'Safety check failed: the EXE is smaller than the video. Embedded media may be missing.' }
Write-Host ''
Write-Host 'SUCCESS: OBEYA.exe was created.' -ForegroundColor Green
Write-Host ('EXE size: {0:N1} MB' -f ($exeBytes/1MB))
Write-Host 'This EXE alone is what you copy to the Desktop. No separate video or HTML is needed at runtime.'
Write-Host 'The compiled EXE has NOT been tested until you launch and verify it on Windows.'
