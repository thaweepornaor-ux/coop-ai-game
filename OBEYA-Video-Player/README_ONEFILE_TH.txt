OBEYA VIDEO PLAYER — MAKE ONE EXE / Windows 10–11
==============================================

เป้าหมาย: ได้ไฟล์ OBEYA.exe ไฟล์เดียวบน Desktop ที่ฝังวิดีโอต้นฉบับครบทั้งไฟล์
ใช้ Microsoft Edge หรือ Google Chrome ที่มีอยู่แล้วใน Windows เปิดหน้าต่างแอปอัตโนมัติ
ใช้งานแบบ Offline โดยเซิร์ฟเวอร์สื่อสารเฉพาะ 127.0.0.1 ในเครื่อง

วิธีทำ (บนเครื่อง Windows ครั้งเดียว)
1. ดาวน์โหลด OBEYA.mp4 และภาพไอคอน OBEYA.png ที่ส่งใน ChatGPT ไปเก็บใน Downloads
   ชื่อ OBEYA(1).mp4 และ Cinematic OBEYA Play Icon(2).png ก็ตรวจพบได้
2. ดาวน์โหลด OBEYA_BUILD_ONE_EXE.cmd และดับเบิลคลิกไฟล์นั้น
   (ตัวสร้างต้องดาวน์โหลดซอร์สขนาดเล็กจาก GitHub ในครั้งแรกเท่านั้น)
3. เมื่อขึ้น SUCCESS จะมี OBEYA.exe อยู่บน Desktop และเปิดเล่นอัตโนมัติ
4. ต่อไปใช้ OBEYA.exe ไฟล์เดียว ดับเบิลคลิกแล้วเห็น Title
   กด START เพื่อเล่นเต็มจอ ไม่ต้องเลือกไฟล์วิดีโออีก

ส่วนที่ฝังใน EXE: OBEYA.html, ไอคอนเดิม และ MP4 ต้นฉบับแบบ byte-for-byte
ไฟล์ MP4 ไม่ถูกแปลง ไม่ถูกบีบอัด และไม่ถูกอัปโหลดขึ้นเว็บไซต์สาธารณะ
การสร้าง EXE ใช้คอมไพเลอร์ .NET Framework ที่มาพร้อม Windows 10/11
ตัวสร้างไม่ใช้ Python, Node.js, ffmpeg หรือ Electron

ระบบควบคุม: START, Pause/Resume, Stop, Mute/Unmute,
ย้อน/ไปหน้า 15 วินาที, Fullscreen/Minimize (ออกจาก Fullscreen),
Exit กลับ Title, Progress Bar และเวลาเล่น

หมายเหตุสำคัญ
- ชุดนี้เป็นโค้ดและตัวสร้าง EXE ยังไม่ใช่ EXE ที่คอมไพล์และผ่านการทดสอบจริง
- Windows 10/11 ต้องมี .NET Framework 4.x พร้อม csc.exe, Edge หรือ Chrome
- เครื่องบริษัทอาจจำกัดการรัน .cmd / PowerShell หรือ EXE ที่ไม่ได้ลงลายเซ็น
- ถ้าไม่พบ OBEYA.mp4 คอมยังไม่ได้ดาวน์โหลดวิดีโอจากแชทมาไว้ใน Downloads
- ไฟล์ที่สร้างจะมีขนาดมากกว่า 410 MB เล็กน้อยเพราะมีวิดีโอต้นฉบับครบ
- หาก Build แจ้ง ERROR จะยังถือว่าไม่ได้ EXE ที่ใช้งานได้
- ไม่ควรนำไปใช้ในห้องประชุมก่อนทดสอบภาพ เสียง และปุ่มทั้งหมดบนเครื่องจริง

ซอร์สไฟล์:
- OBEYA.html
- OBEYA_ONEFILE_Launcher.cs
- BUILD_OBEYA_ONEFILE.ps1
- OBEYA_BUILD_ONE_EXE.cmd

โปรเจ็กต์นี้บันทึกไว้ในสาขา obeya-player-build-kit
ไม่แก้ไขสาขา main และไม่อัปโหลดไฟล์วิดีโอของผู้ใช้เข้า GitHub
