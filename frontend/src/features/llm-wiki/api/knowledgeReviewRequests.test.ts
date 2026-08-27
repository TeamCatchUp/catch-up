import { describe, expect, it, vi } from 'vitest';

const apiMock = vi.hoisted(() => ({ delete: vi.fn() }));

vi.mock('@/shared/api/client', () => ({ default: apiMock }));

import { clearReviewBlockVerdict } from './knowledgeReviewRequests';

describe('clearReviewBlockVerdict', () => {
  it('판정 본문 없이 block verdict 경로에 DELETE를 보낸다', async () => {
    apiMock.delete.mockResolvedValue({});

    await clearReviewBlockVerdict('proposal-1', 3);

    expect(apiMock.delete).toHaveBeenCalledWith('/api/v1/knowledge-review/queue/proposal-1/blocks/3/verdict');
  });
});
