import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DocuBrain - Fullstack RAG Document Assistant',
  description: 'Upload documents and ask questions powered by Retrieval-Augmented Generation (FastAPI + Next.js)',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased bg-slate-50">{children}</body>
    </html>
  );
}
