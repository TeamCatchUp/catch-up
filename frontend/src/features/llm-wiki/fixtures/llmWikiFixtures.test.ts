import { describe, expect, it } from 'vitest';

import type { ReviewItemType } from '../types/llmWikiModel';
import {
  createDocumentRow,
  createReviewQueueItem,
  DOCUMENT_ROW_FIXTURES,
  REVIEW_QUEUE_ITEM_FIXTURES,
  REVIEW_STAT_CARD_FIXTURES,
} from './llmWikiFixtures';

describe('llmWikiFixtures 정합성', () => {
  it('rejected 항목은 rejectionReason이 반드시 있다 (DB CHECK와 동일 불변식)', () => {
    const rejected = REVIEW_QUEUE_ITEM_FIXTURES.filter((item) => item.status === 'rejected');
    // rejected fixture가 사라지면 아래 루프가 0회 돌아 테스트가 공허하게 통과한다 — 존재 자체를 먼저 못박는다
    expect(rejected.length).toBeGreaterThan(0);

    for (const item of rejected) {
      expect(item.rejectionReason).toBeTruthy();
    }
  });

  it('검토 권한은 행마다 갈린다 — 권한 있는 행·없는 행이 모두 표본에 있다', () => {
    // 한쪽만 남으면 버튼 게이트가 화면 경로에서 한 번도 밟히지 않는다
    const flags = REVIEW_QUEUE_ITEM_FIXTURES.map((item) => item.canReview);
    expect(flags).toContain(true);
    expect(flags).toContain(false);
  });

  it('검토 항목 유형은 열린 타입이다 — 미지 값 대입이 컴파일·실행된다', () => {
    const futureType: ReviewItemType = 'link_suggestion'; // 백엔드에 아직 없는 유형
    const item = createReviewQueueItem({ type: futureType });
    expect(item.type).toBe('link_suggestion');
  });

  it('빌더는 기본값 위에 override만 얹는다', () => {
    const row = createDocumentRow({ title: '결제 실패 대응' });
    expect(row.title).toBe('결제 실패 대응');
    expect(row.status).toBe('reviewed');
  });

  it('스탯 카드 fixture는 8/14 시안 확정 4종이다', () => {
    expect(REVIEW_STAT_CARD_FIXTURES).toHaveLength(4);
  });

  // breadcrumbs는 대시보드 행만의 요건이다
  it('문서 행 fixture는 채널 > 폴더 breadcrumbs를 가진다 (대시보드 행 요건)', () => {
    for (const row of DOCUMENT_ROW_FIXTURES) {
      expect(row.breadcrumbs.map((crumb) => crumb.kind)).toEqual(['channel', 'folder']);
    }
  });

  it('문서 행 fixture는 검토 대기 행을 포함한다 (표의 두 번째 상태 표본)', () => {
    // 이 행이 사라지면 검토 대기 배지의 표 노출 경로가 스토리에서 증발한다 — 존재를 못박는다
    expect(DOCUMENT_ROW_FIXTURES.some((row) => row.status === 'pending_review')).toBe(true);
  });

  it('담당자는 복수 계약이다 — 미지정(0인)·단수·복수 행이 모두 표본에 있다', () => {
    const ownerCounts = DOCUMENT_ROW_FIXTURES.map((row) => row.owners.length);
    expect(ownerCounts).toContain(0);
    expect(ownerCounts).toContain(1);
    // 복수 행이 사라지면 owners[]가 사실상 단수로 굳고 계약 회귀를 잡을 표본이 없어진다
    expect(ownerCounts.some((count) => count > 1)).toBe(true);
  });

  it('행의 첫 담당자 이름은 서로 다르다 — 스토리가 담당자 셀을 이름으로 집어 좌표를 잰다', () => {
    const firstOwnerNames = DOCUMENT_ROW_FIXTURES.flatMap((row) => row.owners.slice(0, 1)).map(
      (owner) => owner.displayName,
    );
    expect(new Set(firstOwnerNames).size).toBe(firstOwnerNames.length);
  });
});
