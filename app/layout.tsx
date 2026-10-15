import type { Metadata } from 'next';
import './globals.css';
import './showtime.css';
import './arena-refresh.css';
import './arena-cast-stage.css';
import './host-lobby-fit.css';
import './lobby-showcase.css';
import './answer-voice-controls.css';
import './reveal-audio-status.css';
import './live-cast-space.css';
import './eye-comfort-palette.css';
import './complete-game-art.css';
import './mobile-all-screens.css';
export const metadata: Metadata = { title: 'ประเมินความเข้าใจ AI', description: 'เกมตอบคำถาม 15 ข้อ สำหรับประเมินความเข้าใจ AI แบบสนุก เข้าเล่นได้ด้วย QR Code' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="th"><body>{children}</body></html>;
}
