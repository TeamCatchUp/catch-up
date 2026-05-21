import { describe, expect, it } from 'vitest';

import type { SourceResponseApi as SourceResponse } from '@/shared/types/sourceApi';

import { normalizeChannelTalkFields } from './channelTalk';

const baseUserChat: SourceResponse = {
  id: 'channel_talk:user_chat:ch1:rec1',
  source: 'channel_talk',
  entity_type: 'user_chat',
  title: '홍길동',
  text: '문의 본문',
  author: '담당자A',
  channel_name: '고객문의 채널',
};

const baseArticle: SourceResponse = {
  id: 'channel_talk:document_article:ch1:art1',
  source: 'channel_talk',
  entity_type: 'document_article',
  title: 'FAQ 문서',
  text: '본문',
  author: '저자A',
  channel_name: '채널톡',
  space_name: '도움말 스페이스',
};

describe('normalizeChannelTalkFields', () => {
  describe('user_chat', () => {
    it('repo는 channel_name, title/author는 그대로 매핑한다', () => {
      const result = normalizeChannelTalkFields(baseUserChat);
      expect(result).toEqual({
        repo: '고객문의 채널',
        title: '홍길동',
        author: '담당자A',
      });
    });

    it('channel_name이 null이면 빈 문자열을 흘려보낸다 (UI에서 - fallback)', () => {
      const result = normalizeChannelTalkFields({ ...baseUserChat, channel_name: null });
      expect(result.repo).toBe('');
    });

    it('title이 null이면 빈 문자열', () => {
      const result = normalizeChannelTalkFields({ ...baseUserChat, title: null as unknown as string });
      expect(result.title).toBe('');
    });

    it('author가 null이면 빈 문자열', () => {
      const result = normalizeChannelTalkFields({ ...baseUserChat, author: null });
      expect(result.author).toBe('');
    });

    it('issue_key / github_number는 매핑하지 않는다', () => {
      const result = normalizeChannelTalkFields(baseUserChat);
      expect(result.issue_key).toBeUndefined();
      expect(result.github_number).toBeUndefined();
    });
  });

  describe('document_article', () => {
    it('repo는 space_name을 사용한다 (channel_name이 아닌)', () => {
      const result = normalizeChannelTalkFields(baseArticle);
      expect(result.repo).toBe('도움말 스페이스');
    });

    it('title / author는 그대로 매핑한다', () => {
      const result = normalizeChannelTalkFields(baseArticle);
      expect(result.title).toBe('FAQ 문서');
      expect(result.author).toBe('저자A');
    });

    it('space_name이 null이면 빈 문자열 (channel_name으로 fallback하지 않는다)', () => {
      const result = normalizeChannelTalkFields({
        ...baseArticle,
        space_name: null,
      });
      expect(result.repo).toBe('');
    });

    it('space_name이 undefined여도 빈 문자열', () => {
      const { space_name: _omit, ...rest } = baseArticle;
      const result = normalizeChannelTalkFields(rest);
      expect(result.repo).toBe('');
    });
  });
});
