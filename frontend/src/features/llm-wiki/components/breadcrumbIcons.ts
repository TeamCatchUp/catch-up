import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import type { BreadcrumbKind } from '../types/llmWikiModel';

/**
 * breadcrumb 마디 종류 → 아이콘. WikiPageHeader(헤더 체인)와 DashboardDocumentRow(표 행 체인)가
 * 같은 계약을 렌더하므로 한 곳에서만 정의한다.
 *
 * Figma가 아이콘을 정의한 종류는 채널·폴더 2종뿐이다. 미지 종류는 아이콘을 발명하지 않고
 * 라벨만 렌더한다(DocumentStatusBadge와 같은 규칙) — 그래서 Partial이다.
 *
 * 시안 3개가 아이콘 유무에서 갈린다: 폴더(17762:104786)는 채널 마디에 icon/menu, 문서
 * (17922:56420)는 아이콘 없음, 검토큐(17930:57154)는 wiki_channel + folder. 가장 최근이고
 * 완성도가 높은 검토큐 규칙을 채택했다 — 배치의 행 breadcrumb 계약과도 같다. 나머지 둘의
 * 차이는 디자이너 확인 대상으로 기록했다.
 */
export const BREADCRUMB_ICON: Partial<Record<BreadcrumbKind, typeof IconWikiChannel>> = {
  channel: IconWikiChannel,
  folder: IconFolder,
};
