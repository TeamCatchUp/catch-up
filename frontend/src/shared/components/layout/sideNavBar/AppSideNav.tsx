'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

import { useSidebarStore } from '@/shared/store/sidebarStore';

import HomeSideNav from './HomeSideNav';
import WikiSideNav from './WikiSideNav';

/** LLM Wiki 모드로 렌더할 경로인가 */
export function isWikiRoute(pathname: string): boolean {
  return pathname === '/llm-wiki' || pathname.startsWith('/llm-wiki/');
}

/**
 * 경로로 SNB 모드를 고르는 진입점. 설정 경로에서는 레이아웃이 SNB 자체를 렌더하지 않는다.
 */
export default function AppSideNav() {
  const pathname = usePathname();
  const setSidebarOpen = useSidebarStore((state) => state.setSidebarOpen);

  const isChatRoute = pathname.startsWith('/chat');
  const isAgentEditorRoute = pathname.startsWith('/agent-studio/new');

  // 채팅·에이전트 편집 화면은 본문이 넓어야 해서 진입 시 접는다
  useEffect(() => {
    setSidebarOpen(!isChatRoute && !isAgentEditorRoute);
  }, [isAgentEditorRoute, isChatRoute, setSidebarOpen]);

  return isWikiRoute(pathname) ? <WikiSideNav /> : <HomeSideNav />;
}
