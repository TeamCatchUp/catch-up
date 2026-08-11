import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import type { BreadcrumbKind } from '../types/llmWikiModel';

/**
 * breadcrumb 마디 종류 → 아이콘. 헤더 체인과 표 행 체인이 같은 계약을 쓰므로 한 곳에서만 정의한다.
 * 미지 종류는 아이콘을 발명하지 않고 라벨만 렌더한다 — 그래서 Partial이다.
 */
export const BREADCRUMB_ICON: Partial<Record<BreadcrumbKind, typeof IconWikiChannel>> = {
  channel: IconWikiChannel,
  folder: IconFolder,
};
