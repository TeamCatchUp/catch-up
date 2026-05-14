import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { SourceResponseApi } from '@/shared/types/sourceApi';

import { mapHybridSearchResult } from './mapHybridSearchResult';

const FIXED_NOW = new Date('2026-05-14T12:00:00');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('mapHybridSearchResult', () => {
  it('jira source → integrationLabel "Jira", identifier에 issue_key', () => {
    const src: SourceResponseApi = {
      id: '1',
      source: 'jira',
      entity_type: 'issue',
      title: '결제 롤백 검토',
      text: '...',
      url: 'https://example.atlassian.net/browse/CU-989',
      author: '팀원D',
      updated_at: '2026-05-13T12:00:00',
      project_key: 'CU',
      issue_key: 'CU-989',
    };

    const out = mapHybridSearchResult(src);

    expect(out.sourceType).toBe('jira');
    expect(out.integrationLabel).toBe('Jira');
    expect(out.title).toBe('결제 롤백 검토');
    expect(out.author).toBe('팀원D');
    expect(out.identifier).toBe('[CU-989]');
    expect(out.contextLabel).toBe('CU');
  });

  it('github source → identifier에 #number, contextLabel은 owner/repo', () => {
    const src: SourceResponseApi = {
      id: '2',
      source: 'github',
      entity_type: 'pr',
      title: 'feat: 결제 롤백',
      text: '...',
      url: 'https://github.com/catchup-team/catchup-frontend/pull/1234',
      author: 'fkgrkyr',
      updated_at: '2026-05-11T12:00:00',
      owner: 'catchup-team',
      repo: 'catchup-frontend',
      number: 1234,
    };

    const out = mapHybridSearchResult(src);

    expect(out.sourceType).toBe('github');
    expect(out.integrationLabel).toBe('Github');
    expect(out.contextLabel).toBe('catchup-team/catchup-frontend');
    expect(out.identifier).toBe('#1234');
  });

  it('slack source → contextLabel에 #channel_name, identifier 없음', () => {
    const src: SourceResponseApi = {
      id: '3',
      source: 'slack',
      entity_type: 'message',
      title: '검색 결과 페이지 디자인 리뷰',
      text: '...',
      author: '디자이너',
      updated_at: '2026-05-14T07:00:00',
      channel_name: 'frontend-team',
    };

    const out = mapHybridSearchResult(src);

    expect(out.sourceType).toBe('slack');
    expect(out.integrationLabel).toBe('Slack');
    expect(out.contextLabel).toBe('#frontend-team');
    expect(out.identifier).toBeUndefined();
  });

  it('confluence source → contextLabel에 space_name', () => {
    const src: SourceResponseApi = {
      id: '4',
      source: 'confluence',
      entity_type: 'page',
      title: '하이브리드 검색 사양',
      text: '...',
      author: 'PM',
      updated_at: '2026-05-08T09:00:00',
      space_name: 'CatchUp / 디자인 시스템',
    };

    const out = mapHybridSearchResult(src);

    expect(out.sourceType).toBe('confluence');
    expect(out.integrationLabel).toBe('Confluence');
    expect(out.contextLabel).toBe('CatchUp / 디자인 시스템');
    expect(out.identifier).toBeUndefined();
  });

  it('channel_talk source → contextLabel에 channel_name, integrationLabel "채널톡"', () => {
    const src: SourceResponseApi = {
      id: '5',
      source: 'channel_talk',
      entity_type: 'user_chat',
      title: '검색 결과가 안 보여요',
      text: '...',
      author: '고객',
      updated_at: '2026-05-14T12:00:00',
      channel_name: 'CS / 문의 응대',
    };

    const out = mapHybridSearchResult(src);

    expect(out.sourceType).toBe('channel_talk');
    expect(out.integrationLabel).toBe('채널톡');
    expect(out.contextLabel).toBe('CS / 문의 응대');
  });

  it('updated_at 누락 시 changedAt은 빈 문자열', () => {
    const src: SourceResponseApi = {
      id: '6',
      source: 'jira',
      entity_type: 'issue',
      title: 't',
      text: '',
      author: 'a',
      project_key: 'CU',
    };

    expect(mapHybridSearchResult(src).changedAt).toBe('');
  });

  it('author 누락 시 빈 문자열로 대체', () => {
    const src: SourceResponseApi = {
      id: '7',
      source: 'jira',
      entity_type: 'issue',
      title: 't',
      text: '',
      project_key: 'CU',
    };

    expect(mapHybridSearchResult(src).author).toBe('');
  });

  it('url 누락 시 빈 문자열', () => {
    const src: SourceResponseApi = {
      id: '8',
      source: 'jira',
      entity_type: 'issue',
      title: 't',
      text: '',
      project_key: 'CU',
    };

    expect(mapHybridSearchResult(src).url).toBe('');
  });
});
