'use client';

import { type ReactNode, useEffect } from 'react';
import { usePathname } from 'next/navigation';

import DocSearchModal from '@/shared/components/search/DocSearchModal';
import { useSidebarStore } from '@/shared/store/sidebarStore';

import HomeSideNav from './HomeSideNav';
import WikiSideNav from './WikiSideNav';

/** LLM Wiki 모드로 렌더할 경로인가 */
export function isWikiRoute(pathname: string): boolean {
  return pathname === '/llm-wiki' || pathname.startsWith('/llm-wiki/');
}

interface AppSideNavProps {
  /** 위키 경로에서 쓸 SNB. 데이터 주입이 features 층이라 app 레이아웃이 넣어준다 */
  wikiNav?: ReactNode;
}

/**
 * 경로로 SNB 모드를 고르는 진입점. 설정 경로에서는 레이아웃이 SNB 자체를 렌더하지 않는다.
 * 문서 탐색 모달은 두 SNB가 공유하므로 여기서 한 번만 마운트한다.
 */
export default function AppSideNav({ wikiNav }: AppSideNavProps = {}) {
  const pathname = usePathname();
  const setSidebarOpen = useSidebarStore((state) => state.setSidebarOpen);
  const isDocSearchOpen = useSidebarStore((state) => state.isDocSearchOpen);
  const setDocSearchOpen = useSidebarStore((state) => state.setDocSearchOpen);

  const isChatRoute = pathname.startsWith('/chat');
  const isAgentEditorRoute = pathname.startsWith('/agent-studio/new');

  // 채팅·에이전트 편집 화면은 본문이 넓어야 해서 진입 시 접는다
  useEffect(() => {
    setSidebarOpen(!isChatRoute && !isAgentEditorRoute);
  }, [isAgentEditorRoute, isChatRoute, setSidebarOpen]);

  // 모달에서 결과 페이지로 나가면 열린 채 남지 않는다
  useEffect(() => {
    setDocSearchOpen(false);
  }, [pathname, setDocSearchOpen]);

  // 설정 경로는 SNB째 내려가 모달도 사라진다 — 열림 상태를 남기면 복귀 때 한 번 깜빡인다
  useEffect(() => () => setDocSearchOpen(false), [setDocSearchOpen]);

  return (
    <>
      {isWikiRoute(pathname) ? (wikiNav ?? <WikiSideNav />) : <HomeSideNav />}
      <DocSearchModal open={isDocSearchOpen} onOpenChange={setDocSearchOpen} />
    </>
  );
}
