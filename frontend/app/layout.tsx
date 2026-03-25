import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Interchange AI Dashboard',
  description: 'Dashboard profissional em Next.js para análise de regras de intercâmbio.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
