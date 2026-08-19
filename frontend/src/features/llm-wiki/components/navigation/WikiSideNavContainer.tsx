'use client';

import { useQuery } from '@tanstack/react-query';

import WikiSideNav from '@/shared/components/layout/sideNavBar/WikiSideNav';
import { authQueries } from '@/shared/queries/auth.queries';

import { useWikiSideNav } from '../../hooks/useWikiSideNav';

/** 위키 SNB에 실 데이터를 물리는 자리. shared 층은 features를 import할 수 없어 여기서 잇는다. */
export default function WikiSideNavContainer() {
  const { treeNodes, favorites, channelAdmins, onNodeToggle } = useWikiSideNav();
  const { data: me } = useQuery(authQueries.me());

  return (
    <WikiSideNav
      canCreateWiki={me?.role === 'admin'}
      treeNodes={treeNodes}
      favorites={favorites}
      channelAdmins={channelAdmins}
      onNodeToggle={onNodeToggle}
    />
  );
}
