@echo off
setlocal
title OBEYA - Change Desktop Icon
set "OBEYA_FIX_SELF=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:OBEYA_FIX_SELF); $m='__OBEYA_ICON_SCRIPT_START__'; $i=$s.LastIndexOf($m); if($i -lt 0){throw 'Installer content missing'}; Invoke-Expression ($s.Substring($i+$m.Length))"
if errorlevel 1 (
 echo.
 echo Please read the error message above.
 pause
 exit /b 1
)
echo.
echo DONE. Use the NEW OBEYA Video Player icon on Desktop.
pause
exit /b 0
__OBEYA_ICON_SCRIPT_START__
$ErrorActionPreference='Stop'
try {
 Add-Type -AssemblyName System.Drawing
 $desktop=[Environment]::GetFolderPath('DesktopDirectory')
 $downloads=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
 $app=Join-Path $env:LOCALAPPDATA 'OBEYA Video Player'
 $here=Split-Path -Parent $env:OBEYA_FIX_SELF
 $folders=@($here,$downloads,$desktop,(Join-Path $desktop 'OBEYA'),$app) | Select-Object -Unique
 function SearchOBEYA([string]$pattern) {
   foreach($dir in $folders){
     if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
     $files=@(Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Where-Object {$_.Name -match $pattern} | Sort-Object LastWriteTime -Descending)
     if($files.Count -gt 0){return $files[0]}
   }
   return $null
 }
 $png=SearchOBEYA '^(OBEYA(?:_ICON)?(?:\s*\(\d+\))?|Cinematic OBEYA Play Icon(?:\s*\(\d+\))?)\.png$'
 $html=SearchOBEYA '^OBEYA(?:_READY_OFFLINE|_PLAYER_CUSTOM_ICON)?(?:\s*\(\d+\))?\.html$'
 if(!$png){throw 'Please save the OBEYA woman PNG icon from ChatGPT into Downloads, then run this file again.'}
 if(!$html){throw 'OBEYA_READY_OFFLINE.html was not found in Downloads/Desktop. Download or move it to Downloads, then retry.'}
 if(!(Test-Path -LiteralPath $app)){New-Item -ItemType Directory -Path $app -Force | Out-Null}
 $ico=Join-Path $app 'OBEYA.ico'
 $img=[System.Drawing.Image]::FromFile($png.FullName)
 try {
   $sizes=@(16,32,48,64,128,256)
   $entries=New-Object 'System.Collections.Generic.List[byte[]]'
   foreach($n in $sizes){
     $bmp=New-Object System.Drawing.Bitmap -ArgumentList $n,$n
     $g=[System.Drawing.Graphics]::FromImage($bmp)
     try {
       $g.Clear([System.Drawing.Color]::Transparent)
       $g.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
       $g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::HighQuality
       $scale=[Math]::Min($n/[double]$img.Width,$n/[double]$img.Height)
       $w=[int][Math]::Round($img.Width*$scale)
       $h=[int][Math]::Round($img.Height*$scale)
       $g.DrawImage($img,[int](($n-$w)/2),[int](($n-$h)/2),$w,$h)
       $mem=New-Object System.IO.MemoryStream
       try{$bmp.Save($mem,[System.Drawing.Imaging.ImageFormat]::Png);$entries.Add($mem.ToArray())}
       finally{$mem.Dispose()}
     }finally{$g.Dispose();$bmp.Dispose()}
   }
   $stream=[System.IO.File]::Create($ico)
   $writer=New-Object System.IO.BinaryWriter($stream)
   try {
     $writer.Write([UInt16]0);$writer.Write([UInt16]1);$writer.Write([UInt16]$sizes.Count)
     $offset=6+16*$sizes.Count
     for($i=0;$i -lt $sizes.Count;$i++){
       $n=$sizes[$i]
       $writer.Write([byte]$(if($n -eq 256){0}else{$n}))
       $writer.Write([byte]$(if($n -eq 256){0}else{$n}))
       $writer.Write([byte]0);$writer.Write([byte]0)
       $writer.Write([UInt16]1);$writer.Write([UInt16]32)
       $writer.Write([UInt32]$entries[$i].Length)
       $writer.Write([UInt32]$offset)
       $offset+=$entries[$i].Length
     }
     foreach($bytes in $entries){$writer.Write($bytes)}
     $writer.Flush()
   }finally{$writer.Dispose()}
 }finally{$img.Dispose()}
 $video=SearchOBEYA '^OBEYA(?:\s*\(\d+\))?\.mp4$'
 $player=$html.FullName
 if($video){
   $target=Join-Path $video.DirectoryName 'OBEYA_PLAYER_READY.html'
   if($html.FullName -ine $target){Copy-Item -LiteralPath $html.FullName -Destination $target -Force}
   $player=$target
   Write-Host ('Video detected: '+$video.Name)
 }else{
   Write-Host 'Note: The MP4 was not found in Downloads/Desktop. Shortcut will use your existing HTML path.' -ForegroundColor Yellow
 }
 $pf86=[Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
 $paths=@()
 foreach($dir in @($pf86,$env:ProgramFiles,$env:LOCALAPPDATA)){
   if($dir){
     $paths+=(Join-Path $dir 'Microsoft\Edge\Application\msedge.exe')
     $paths+=(Join-Path $dir 'Google\Chrome\Application\chrome.exe')
   }
 }
 $browser=$paths | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf} | Select-Object -First 1
 if(!$browser){throw 'Microsoft Edge or Google Chrome could not be found.'}
 $lnk=Join-Path $desktop 'OBEYA Video Player.lnk'
 $sh=New-Object -ComObject WScript.Shell
 $shortcut=$sh.CreateShortcut($lnk)
 $shortcut.TargetPath=$browser
 $shortcut.Arguments='--app="'+([System.Uri]$player).AbsoluteUri+'" --new-window'
 $shortcut.WorkingDirectory=Split-Path -Parent $player
 $shortcut.IconLocation=$ico+',0'
 $shortcut.Description='OBEYA Video Player'
 $shortcut.Save()
 if(!(Test-Path -LiteralPath $lnk)){throw 'Could not create Desktop shortcut.'}
 Write-Host 'Success! Your NEW OBEYA Video Player Desktop icon uses your original silver-hair image.' -ForegroundColor Green
 Write-Host ('Desktop shortcut: '+$lnk)
 exit 0
}catch{
 Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
 exit 1
}
