import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'ภารกิจ AI ในสหกรณ์', description: 'เกมประเมินความเข้าใจพื้นฐาน AI สำหรับงานสหกรณ์' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="th"><body>{children}</body></html>;
}
