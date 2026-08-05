import { describe, expect, it } from 'vitest';

import { CONNECTOR_CATEGORIES, CONNECTOR_CONTENT } from './connectorContent';

describe('CONNECTOR_CONTENT', () => {
  it('도구 5종을 모두 담는다', () => {
    expect(Object.keys(CONNECTOR_CONTENT).sort()).toEqual(
      ['channel_talk', 'confluence', 'github', 'jira', 'slack'].sort(),
    );
  });

  it('카탈로그 설명은 도구마다 다르다 — Figma에 5종 실제 값이 있다', () => {
    const descriptions = Object.values(CONNECTOR_CONTENT).map((c) => c.catalogDescription);
    expect(new Set(descriptions).size).toBe(5);
  });

  it('Slack 카피는 Figma 실측값과 일치한다', () => {
    expect(CONNECTOR_CONTENT.slack.catalogDescription).toBe('채팅에 흩어진 결정과 답을 다시 찾아요');
    expect(CONNECTOR_CONTENT.slack.headerDescription).toBe('채팅 스레드에 묻힌 결정을 다시 꺼내오세요');
    expect(CONNECTOR_CONTENT.slack.guideLabel).toBe('Slack 연동 가이드 보기');
  });

  it('연동 범위는 4행이고 라벨 순서가 고정이다', () => {
    for (const content of Object.values(CONNECTOR_CONTENT)) {
      expect(content.scope.map((row) => row.label)).toEqual(['무엇을', '어디까지', '언제·어떻게', '누가 볼 수 있나']);
    }
  });

  it('예시 질문은 3개 고정, 대조 항목은 도구별 가변이되 비어 있지 않다', () => {
    // 대조 항목(연동돼요/안 돼요)은 도구마다 1~4개로 다르다 — Slack만 Figma 실측(3개)이고
    // 나머지는 의도된 초안 카피다. ScopeCompareCard는 개수 가변을 그대로 렌더한다.
    for (const content of Object.values(CONNECTOR_CONTENT)) {
      expect(content.sampleQuestions).toHaveLength(3);
      expect(content.included.length).toBeGreaterThan(0);
      expect(content.excluded.length).toBeGreaterThan(0);
    }
  });

  it('카테고리는 3종이고 각 카테고리에 도구가 최소 1개 있다', () => {
    expect(CONNECTOR_CATEGORIES).toEqual(['커뮤니케이션', '문서 · 지식', '개발 · 이슈 관리']);
    for (const category of CONNECTOR_CATEGORIES) {
      const tools = Object.values(CONNECTOR_CONTENT).filter((c) => c.category === category);
      expect(tools.length).toBeGreaterThan(0);
    }
  });

  it('가이드 라벨은 도구명을 포함한다', () => {
    for (const content of Object.values(CONNECTOR_CONTENT)) {
      expect(content.guideLabel).toContain(content.name);
    }
  });
});
