@echo off
setlocal
title OBEYA - Replace Edge icon on Desktop
set "OBEYA_ICON_SELF=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText($env:OBEYA_ICON_SELF);$m='__OBEYA_PS_DATA__';$p=$t.LastIndexOf($m);if($p -lt 0){throw 'Script data missing'};Invoke-Expression $t.Substring($p+$m.Length)"
if errorlevel 1 (
 echo.
 echo OBEYA was not changed. Please see the error above.
 pause
 exit /b 1
)
echo.
echo OBEYA Desktop icon was replaced. You may close this window.
pause
exit /b 0
__OBEYA_PS_DATA__
$ErrorActionPreference='Stop'
try {
 Add-Type -AssemblyName System.Drawing
 $desktop=[Environment]::GetFolderPath('DesktopDirectory')
 $downloads=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
 $here=Split-Path -Parent $env:OBEYA_ICON_SELF
 $app=Join-Path $env:LOCALAPPDATA 'OBEYA Video Player'
 $folders=@($desktop,$downloads,$here,(Join-Path $desktop 'OBEYA'),(Join-Path $downloads 'OBEYA'),$app) | Select-Object -Unique
 function Find-One([string]$pattern) {
   foreach($dir in $folders) {
     if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
     $hits=@(Get-ChildItem -LiteralPath $dir -File -Force -ErrorAction SilentlyContinue | Where-Object {$_.Name -match $pattern} | Sort-Object LastWriteTime -Descending)
     if($hits.Count -gt 0){return $hits[0]}
   }
   return $null
 }
 $html=Find-One '^OBEYA(?:_READY_OFFLINE|_PLAYER_CUSTOM_ICON|_PLAYER_READY)?(?:\s*\(\d+\))?\.html$'
 $png=Find-One '^(?:OBEYA(?:_ICON)?|Cinematic OBEYA Play Icon)(?:\s*\(\d+\))?\.png$'
 if(!$html){throw 'Cannot find OBEYA_READY_OFFLINE.html. Put it on Desktop or in Downloads.'}
 if(!$png){throw 'Cannot find OBEYA PNG image. Save the silver-hair OBEYA picture from ChatGPT as OBEYA.png to Downloads.'}
 if(!(Test-Path -LiteralPath $app)){New-Item -Path $app -ItemType Directory -Force | Out-Null}
 $ico=Join-Path $app 'OBEYA.ico'

 $img=[System.Drawing.Image]::FromFile($png.FullName)
 try {
   $sizes=@(16,24,32,48,64,128,256)
   $entries=New-Object 'System.Collections.Generic.List[byte[]]'
   foreach($side in $sizes) {
     $bmp=New-Object System.Drawing.Bitmap -ArgumentList $side,$side
     $graphics=[System.Drawing.Graphics]::FromImage($bmp)
     try {
       $graphics.Clear([System.Drawing.Color]::Transparent)
       $graphics.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
       $graphics.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::HighQuality
       $scale=[Math]::Min($side/[double]$img.Width,$side/[double]$img.Height)
       $w=[int][Math]::Round($img.Width*$scale)
       $h=[int][Math]::Round($img.Height*$scale)
       $graphics.DrawImage($img,[int](($side-$w)/2),[int](($side-$h)/2),$w,$h)
       $mem=New-Object IO.MemoryStream
       try{$bmp.Save($mem,[System.Drawing.Imaging.ImageFormat]::Png);$entries.Add($mem.ToArray())}finally{$mem.Dispose()}
     }finally{$graphics.Dispose();$bmp.Dispose()}
   }
   $stream=[IO.File]::Create($ico)
   $out=New-Object IO.BinaryWriter($stream)
   try {
     $out.Write([UInt16]0);$out.Write([UInt16]1);$out.Write([UInt16]$sizes.Count)
     $offset=6+16*$sizes.Count
     for($i=0;$i -lt $sizes.Count;$i++){
       $n=$sizes[$i]
       $out.Write([byte]$(if($n -eq 256){0}else{$n}))
       $out.Write([byte]$(if($n -eq 256){0}else{$n}))
       $out.Write([byte]0);$out.Write([byte]0)
       $out.Write([UInt16]1);$out.Write([UInt16]32)
       $out.Write([UInt32]$entries[$i].Length)
       $out.Write([UInt32]$offset)
       $offset+=$entries[$i].Length
     }
     foreach($bytes in $entries){$out.Write($bytes)}
     $out.Flush()
   }finally{$out.Dispose()}
 }finally{$img.Dispose()}
 $pf86=[Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
 $paths=@()
 foreach($dir in @($pf86,$env:ProgramFiles,$env:LOCALAPPDATA)){
   if($dir){
     $paths+=Join-Path $dir 'Microsoft\Edge\Application\msedge.exe'
     $paths+=Join-Path $dir 'Google\Chrome\Application\chrome.exe'
   }
 }
 $browser=$paths | Where-Object{Test-Path -LiteralPath $_ -PathType Leaf} | Select-Object -First 1
 if(!$browser){throw 'Microsoft Edge or Google Chrome was not found.'}

 $link=Join-Path $desktop 'OBEYA Video Player.lnk'
 $ws=New-Object -ComObject WScript.Shell
 $shortcut=$ws.CreateShortcut($link)
 $shortcut.TargetPath=$browser
 $shortcut.Arguments='--app="'+([Uri]$html.FullName).AbsoluteUri+'" --new-window'
 $shortcut.WorkingDirectory=$html.DirectoryName
 $shortcut.IconLocation=$ico+',0'
 $shortcut.Description='OBEYA Video Player'
 $shortcut.Save()
 if(!(Test-Path -LiteralPath $link)){throw 'Could not create OBEYA shortcut.'}
 # Hide ONLY the original desktop HTML icon, never delete it.
 # The new custom-icon shortcut continues to open the hidden original file.
 if($html.DirectoryName -ieq $desktop) {
   $file=Get-Item -LiteralPath $html.FullName -Force
   $file.Attributes=$file.Attributes -bor [IO.FileAttributes]::Hidden
   Write-Host 'The old Edge HTML icon was hidden (not deleted).' -ForegroundColor Cyan
 }
 Write-Host 'SUCCESS: New OBEYA Video Player icon is on Desktop.' -ForegroundColor Green
 Write-Host ('Icon: '+$png.Name)
 Write-Host ('HTML unchanged: '+$html.FullName)
 Write-Host 'Double-click OBEYA Video Player, NOT the old HTML.'
 exit 0
}catch{
 Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
 exit 1
}
