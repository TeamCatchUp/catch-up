// dev 전용 route group — (app)/(auth) 형제. 앱 크롬·인증 게이트를 상속하지 않는다.
// 프로덕션 빌드에서는 notFound() 로 노출 차단. QueryProvider/ThemeProvider 는 root layout 제공.

import { notFound } from 'next/navigation';

export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === 'production') notFound();

  return <div className="bg-fill-normal min-h-screen">{children}</div>;
}
