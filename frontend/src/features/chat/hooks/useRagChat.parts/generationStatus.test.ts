import { beforeEach, describe, expect, it, vi } from 'vitest';

import chatService from '@/features/chat/services/chatService';

import { getGenerationStatusOrIdle } from './generationStatus';

vi.mock('@/features/chat/services/chatService', () => ({
  default: {
    getGenerationStatus: vi.fn(),
  },
}));

const getGenerationStatusMock = vi.mocked(chatService.getGenerationStatus);

describe('getGenerationStatusOrIdle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns backend generation status when status lookup succeeds', async () => {
    getGenerationStatusMock.mockResolvedValueOnce({
      is_generating: true,
      cutoff_id: '1710000000000-0',
    });

    await expect(getGenerationStatusOrIdle('session-1')).resolves.toEqual({
      is_generating: true,
      cutoff_id: '1710000000000-0',
    });

    expect(getGenerationStatusMock).toHaveBeenCalledWith('session-1');
  });

  it('returns idle generation status when status lookup fails', async () => {
    getGenerationStatusMock.mockRejectedValueOnce(new Error('status unavailable'));

    await expect(getGenerationStatusOrIdle('session-1')).resolves.toEqual({
      is_generating: false,
      cutoff_id: null,
    });
  });

  it('does not log status fallback failures to console', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    getGenerationStatusMock.mockRejectedValueOnce(new Error('status unavailable'));

    await getGenerationStatusOrIdle('session-1');

    expect(warnSpy).not.toHaveBeenCalled();
    expect(errorSpy).not.toHaveBeenCalled();

    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });
});
