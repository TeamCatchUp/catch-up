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

  it('confidence는 0~1 범위다 (knowledge_*_candidates.confidence)', () => {
    for (const item of REVIEW_QUEUE_ITEM_FIXTURES) {
      expect(item.confidence).toBeGreaterThanOrEqual(0);
      expect(item.confidence).toBeLessThanOrEqual(1);
    }
  });

  it('검토 항목 유형은 열린 타입이다 — 미지 값 대입이 컴파일·실행된다', () => {
    const futureType: ReviewItemType = 'link_suggestion'; // 명세 6유형 대비, 백엔드엔 아직 없음
    const item = createReviewQueueItem({ type: futureType });
    expect(item.type).toBe('link_suggestion');
  });

  it('빌더는 기본값 위에 override만 얹는다', () => {
    const row = createDocumentRow({ title: '결제 실패 대응' });
    expect(row.title).toBe('결제 실패 대응');
    expect(row.status).toBe('reviewed');
  });

  it('스탯 카드 fixture는 Figma 확정 4종이다', () => {
    expect(REVIEW_STAT_CARD_FIXTURES).toHaveLength(4);
  });

  // 3화면 공용 전제는 Figma 재확인에서 깨졌다 — breadcrumbs는 대시보드 행만의 요건으로 남는다
  it('문서 행 fixture는 채널 > 폴더 breadcrumbs를 가진다 (대시보드 행 요건)', () => {
    for (const row of DOCUMENT_ROW_FIXTURES) {
      expect(row.breadcrumbs.map((crumb) => crumb.kind)).toEqual(['channel', 'folder']);
    }
  });
});
