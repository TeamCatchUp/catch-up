// dev 전용 route group — (app)/(auth) 형제. 앱 크롬·인증 게이트를 상속하지 않는다.
// production 노출됨 (Storybook 대용). 삭제 절차는 ./README.md 참고.

import { notFound } from 'next/navigation';

export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === 'production') notFound();

  return <div className="bg-fill-normal min-h-screen">{children}</div>;
}
