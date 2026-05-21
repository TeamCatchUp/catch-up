import { describe, expect, it } from 'vitest';

import type { SourceResponseApi as SourceResponse } from '@/shared/types/sourceApi';

import { normalizeSources } from './normalizeRagSources';

describe('normalizeRagSources', () => {
  it('channel_talk source를 channelTalk normalizer로 분기한다', () => {
    const sources: SourceResponse[] = [
      {
        id: 'channel_talk:user_chat:ch1:rec1',
        source: 'channel_talk',
        entity_type: 'user_chat',
        title: '홍길동',
        text: '문의 본문',
        author: '담당자A',
        channel_name: '고객문의',
      },
    ];

    const [result] = normalizeSources(sources);
    expect(result.source_type).toBe('channel_talk');
    expect(result.entity_type).toBe('user_chat');
    expect(result.repo).toBe('고객문의');
    expect(result.title).toBe('홍길동');
    expect(result.author).toBe('담당자A');
  });

  it('document_article 케이스도 정상 분기하고 repo는 space_name을 사용한다', () => {
    const sources: SourceResponse[] = [
      {
        id: 'channel_talk:document_article:ch1:art1',
        source: 'channel_talk',
        entity_type: 'document_article',
        title: 'FAQ',
        text: '본문',
        author: '저자A',
        channel_name: '채널톡',
        space_name: '도움말 스페이스',
      },
    ];

    const [result] = normalizeSources(sources);
    expect(result.source_type).toBe('channel_talk');
    expect(result.entity_type).toBe('document_article');
    expect(result.repo).toBe('도움말 스페이스');
    expect(result.title).toBe('FAQ');
  });

  it('jira source는 기존 동작을 유지한다 (regression)', () => {
    const sources: SourceResponse[] = [
      {
        id: 'jira:issue:CAT-1',
        source: 'jira',
        entity_type: 'issue',
        title: '[CAT-1] 테스트 이슈',
        text: '본문',
        author: '리포터',
        issue_key: 'CAT-1',
        project_key: 'CAT',
      },
    ];

    const [result] = normalizeSources(sources);
    expect(result.source_type).toBe('jira');
    expect(result.issue_key).toBe('CAT-1');
    expect(result.repo).toBe('CAT');
  });

  it('github source는 기존 동작을 유지한다 (regression)', () => {
    const sources: SourceResponse[] = [
      {
        id: 'github:pr:foo/bar:42',
        source: 'github',
        entity_type: 'pr',
        title: 'PR 제목',
        text: '본문',
        author: '작성자',
        owner: 'foo',
        repo: 'bar',
        number: 42,
      },
    ];

    const [result] = normalizeSources(sources);
    expect(result.source_type).toBe('github');
    expect(result.github_number).toBe(42);
    expect(result.repo).toBe('foo/bar');
  });
});
