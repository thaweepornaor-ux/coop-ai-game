import type { Metadata } from 'next';
import './globals.css';
import './showtime.css';
import './arena-refresh.css';
export const metadata: Metadata = { title: 'ประเมินความเข้าใจ AI', description: 'เกมตอบคำถาม 15 ข้อ สำหรับประเมินความเข้าใจ AI แบบสนุก เข้าเล่นได้ด้วย QR Code' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="th"><body>{children}</body></html>;
}
