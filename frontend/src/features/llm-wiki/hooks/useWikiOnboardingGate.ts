'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { authQueries } from '@/shared/queries/auth.queries';

import { wikiQueries } from '../queries/wiki.queries';

export const WIKI_ONBOARDING_PATH = '/llm-wiki/onboarding';
export const WIKI_DASHBOARD_PATH = '/llm-wiki';

/** 채널이 하나도 없는 관리자는 대시보드에 볼 것이 없어 생성 화면으로 보낸다. */
export function shouldStartWikiOnboarding(role: string | undefined, channelCount: number | undefined): boolean {
  return role === 'admin' && channelCount === 0;
}

interface WikiOnboardingGate {
  /** 판정에 필요한 응답이 아직 없거나 이동 중이다 — 화면을 그리지 않는다 */
  blocked: boolean;
}

/**
 * 대시보드용 게이트. 채널 0개인 관리자를 온보딩으로 replace한다.
 * 채널 목록이 도착한 뒤 판정해 대시보드가 잠깐 보였다 튕기는 일을 막는다.
 */
export function useWikiOnboardingGate(): WikiOnboardingGate {
  const router = useRouter();
  const meQuery = useQuery(authQueries.me());
  const channelsQuery = useQuery(wikiQueries.channels());

  const redirecting = shouldStartWikiOnboarding(meQuery.data?.role, channelsQuery.data?.channels.length);

  useEffect(() => {
    // replace라 뒤로가기가 대시보드로 돌아오지 않는다 — 돌아오면 다시 튕긴다
    if (redirecting) router.replace(WIKI_ONBOARDING_PATH);
  }, [redirecting, router]);

  // 조회 실패는 통과시킨다 — 판정할 수 없다고 화면을 막으면 빠져나갈 길이 없다
  return { blocked: redirecting || channelsQuery.isPending || meQuery.isPending };
}

/** 온보딩 화면용 게이트. 관리자가 아니면 대시보드로 돌려보낸다. */
export function useWikiOnboardingAdminGuard(): WikiOnboardingGate {
  const router = useRouter();
  const meQuery = useQuery(authQueries.me());

  const denied = meQuery.data !== undefined && meQuery.data.role !== 'admin';

  useEffect(() => {
    if (denied) router.replace(WIKI_DASHBOARD_PATH);
  }, [denied, router]);

  return { blocked: denied || meQuery.isPending };
}
