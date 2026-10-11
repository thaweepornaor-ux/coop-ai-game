# ภารกิจ AI ในสหกรณ์

เกมตอบคำถาม AI สำหรับผู้สอนและผู้เรียน: 15 ข้อ ข้อละ 15 วินาที ผู้สอนเป็นผู้ควบคุมการเริ่มข้อ เปิดเฉลย ไปต่อ และรีเซ็ต ผู้เรียนตั้งชื่อ เลือกตัวละคร และตอบผ่านมือถือได้

## สถานะการกู้โค้ด

นำ source จาก checkpoint เดิมมาประกอบกับ avatar patch ใน branch `codex/game-recovery` เพื่อทดสอบและพัฒนาต่อ คลังนี้ยังไม่ใช่เกมฉบับพร้อมส่งมอบ และยังไม่มี deployment จาก GitHub

มี frontend, API, กติกาเกม, คำถาม, SQL migration, ตัวเลือกชาย 10 แบบ/หญิง 10 แบบ และข้อมูลแต่งตัว 11 fields ตัว renderer ในชุดกู้ยังเป็นฐานเก่าที่ต้องเปลี่ยนเป็นโมเดลสามมิติคุณภาพดีพร้อมข้อต่อและ animation จริง

ไฟล์ build integration สำหรับ Sites บางส่วนและ schema/config ประกอบยังขาดอยู่ route โลโก้ยังอ้างถึงไฟล์ภาพต้นฉบับที่ไม่ได้รวมในชุด public นี้ จึงยังไม่ถือว่า build ผ่าน

## การตรวจสอบ

GitHub Actions จะตรวจการรัน Node และ CLI ตัวตรวจ GLB ก่อน จากนั้นจึงเพิ่มการทดสอบกติกาและตัวละครจาก source ที่กู้ได้ ผลสำเร็จของ helper ไม่ใช่การยืนยันคุณภาพโมเดลหรือภาพในเกม

ตัวตรวจ GLB แบบอ่านอย่างเดียวอยู่ที่ `scripts/validate-avatar-production-glb.mjs`:

```text
node scripts/validate-avatar-production-glb.mjs --self-test
node scripts/validate-avatar-production-glb.mjs path/to/avatar.glb
```

ไม่รวม credentials, runtime tokens, ข้อมูลผู้เรียนจริง หรือ config ผูกกับ Site เดิมในคลังนี้
