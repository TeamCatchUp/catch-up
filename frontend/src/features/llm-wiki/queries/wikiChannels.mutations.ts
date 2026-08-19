import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import { wikiQueries } from './wiki.queries';

export interface RenameWikiChannelVariables {
  channelId: string;
  name: string;
}

export interface RenameWikiFolderVariables {
  /** 폴더 경로가 채널 아래에 있어 소속 채널 id가 함께 필요하다 */
  channelId: string;
  folderId: string;
  name: string;
}

/**
 * 채널 이름 변경(채널 관리자). 성공 시 채널 목록만 다시 읽는다 —
 * 트리의 채널·폴더 이름이 그 응답에서 온다. 응답 본문은 쓰지 않는다.
 */
export const useRenameWikiChannelMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ channelId, name }: RenameWikiChannelVariables): Promise<void> => {
      await api.patch(API.wiki.channel(channelId), { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: wikiQueries.channels().queryKey });
    },
    // 409 이름 중복은 서버 문구를 그대로 띄운다 — 프론트가 문구를 만들지 않는다
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};

/** 폴더 이름 변경(채널 관리자). 무효화·실패 처리는 채널 이름 변경과 같다. */
export const useRenameWikiFolderMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ channelId, folderId, name }: RenameWikiFolderVariables): Promise<void> => {
      await api.patch(API.wiki.folder(channelId, folderId), { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: wikiQueries.channels().queryKey });
    },
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
