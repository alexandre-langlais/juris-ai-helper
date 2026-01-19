import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'JurisAnnotate AI',
  description: 'Annotation automatique de contrats PDF par IA',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className={inter.className}>
        <main className="min-h-screen bg-gradient-to-b from-background to-muted/20">
          {children}
        </main>
      </body>
    </html>
  );
}
