'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import Cancel from '@/public/icons/icon/cancel.svg';
import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { IntegrationService } from '@/shared/types/integrationService';

import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type {
  SyncableConfluenceSpace,
  SyncableEntity,
  SyncableGithubRepo,
  SyncableJiraProject,
} from '../../../types/api';

const PERIOD_OPTIONS = ['1개월', '3개월', '6개월', '1년', '3년'] as const;

const PERIOD_TO_DAYS: Record<string, number> = {
  '1개월': 30,
  '3개월': 90,
  '6개월': 180,
  '1년': 365,
  '3년': 1095,
};

/** 서비스별 항목 용어 */
const getItemLabel = (service: IntegrationService) => (service === 'github' ? 'Repository' : 'Space');

/** SyncableEntity에서 표시명 추출 */
const getEntityName = (entity: SyncableEntity): string => {
  if ('full_name' in entity) return (entity as SyncableGithubRepo).full_name;
  if ('project_name' in entity)
    return `${(entity as SyncableJiraProject).project_key}: ${(entity as SyncableJiraProject).project_name}`;
  if ('space_name' in entity) return (entity as SyncableConfluenceSpace).space_name;
  return String(entity);
};

/** SyncableEntity에서 고유 ID 추출 */
const getEntityId = (entity: SyncableEntity): string => {
  if ('repo_id' in entity) return String((entity as SyncableGithubRepo).repo_id);
  if ('project_key' in entity) return (entity as SyncableJiraProject).project_key;
  if ('space_key' in entity) return (entity as SyncableConfluenceSpace).space_key;
  return getEntityName(entity);
};

interface SyncableItem {
  id: string;
  name: string;
  parentId: string;
  entity: SyncableEntity;
}

/** 서비스별 sync/full API 호출 생성 */
const buildSyncCall = (service: IntegrationService, parentId: string, groupItems: SyncableItem[], syncDays: number) => {
  switch (service) {
    case 'github':
      return api.post(API.github.syncFull, {
        installation_id: Number(parentId),
        repo_ids: groupItems.map((i) => (i.entity as SyncableGithubRepo).repo_id),
        sync_days: syncDays,
      });
    case 'jira':
      return api.post(API.jira.syncFull, {
        cloud_id: parentId,
        project_keys: groupItems.map((i) => (i.entity as SyncableJiraProject).project_key),
        sync_days: syncDays,
      });
    case 'confluence':
      return api.post(API.confluence.syncFull, {
        cloud_id: parentId,
        space_keys: groupItems.map((i) => (i.entity as SyncableConfluenceSpace).space_key),
        sync_days: syncDays,
      });
    case 'slack':
      return api.post(API.slack.syncFull, {
        team_id: parentId,
        sync_days: syncDays,
      });
  }
};

interface EmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  service: IntegrationService;
  serviceName: string;
}

interface SlackInstallationStatus {
  installed: boolean;
  workspaces: { team_id: string; team_name: string }[];
}

/** 임베딩 모달 */
const EmbeddingModal = ({ open, onOpenChange, service, serviceName }: EmbeddingModalProps) => {
  const isSlack = service === 'slack';
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1개월');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

  const { data: syncableData, isLoading } = useQuery({
    ...adminConnectorQueries.syncable(service),
    enabled: open && !isSlack,
  });

  const { data: slackStatus } = useQuery<SlackInstallationStatus>({
    queryKey: ['slack', 'installationStatus'],
    queryFn: async () => {
      const res = await api.get<SlackInstallationStatus>(API.slack.status);
      return res.data;
    },
    enabled: open && isSlack,
  });

  const items = useMemo<SyncableItem[]>(() => {
    if (!syncableData) return [];
    return Object.entries(syncableData).flatMap(([parentId, entities]) =>
      entities.map((entity) => ({
        id: getEntityId(entity),
        name: getEntityName(entity),
        parentId,
        entity,
      })),
    );
  }, [syncableData]);

  const syncMutation = useMutation({
    mutationKey: ['admin', 'connector', 'syncFull', service] as const,
    mutationFn: async (params: { syncDays: number; selected: SyncableItem[] }) => {
      if (isSlack) {
        const teamId = slackStatus?.workspaces[0]?.team_id;
        if (!teamId) throw new Error('Slack team_id not found');
        return api.post(API.slack.syncFull, { team_id: teamId, sync_days: params.syncDays });
      }

      const groups: Record<string, SyncableItem[]> = {};
      for (const item of params.selected) {
        (groups[item.parentId] ??= []).push(item);
      }

      await Promise.all(
        Object.entries(groups).map(([parentId, groupItems]) =>
          buildSyncCall(service, parentId, groupItems, params.syncDays),
        ),
      );
    },
    // onSuccess/onError 제거: 모달이 즉시 닫혀 unmount 후 콜백 실행 불가
  });

  const itemLabel = getItemLabel(service);
  const isSubmitDisabled = !isSlack && selectedItems.size === 0;

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const resetFormState = () => {
    setSelectedPeriod('1개월');
    setSelectedItems(new Set());
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) resetFormState();
    onOpenChange(nextOpen);
  };

  const handleClose = () => handleDialogOpenChange(false);

  const handleSubmit = () => {
    const syncDays = PERIOD_TO_DAYS[selectedPeriod] ?? 30;
    const selected = items.filter((item) => selectedItems.has(item.id));

    // Fire-and-forget: mutation은 MutationCache에서 unmount 후에도 계속 실행됨
    syncMutation.mutate({ syncDays, selected });

    toast('임베딩이 시작되었습니다.', {
      description: '준비가 끝나면 즉시 알려드릴게요.',
    });
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent
        hideClose
        className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-gray-80">
            {isSlack ? `${serviceName} 임베딩` : `임베딩 할 ${serviceName} ${itemLabel} 선택하기`}
          </DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-gray-50" />
          </button>
        </div>

        <div className="border-neutral-3 w-full border-t pt-4">
          <div className="flex flex-col gap-4">
            {/* 기간 선택 */}
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-1">
                <span className="text-body-small text-gray-90">등록 사유를 선택해주세요.</span>
                <span className="block size-[5px] shrink-0 rounded-full bg-red-50" />
              </div>
              <div className="flex gap-2">
                {PERIOD_OPTIONS.map((period) => (
                  <button
                    key={period}
                    type="button"
                    onClick={() => setSelectedPeriod(period)}
                    className={`text-body-small h-9 cursor-pointer rounded-full px-3 ${
                      selectedPeriod === period ? 'bg-gray-80 text-white' : 'border-neutral-3 text-gray-60 border'
                    }`}
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>

            {/* Space/Repository 선택 (Slack 제외) */}
            {!isSlack && (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-body-small text-gray-90">{itemLabel}를 선택해주세요.</span>
                  <span className="block size-[5px] shrink-0 rounded-full bg-red-50" />
                </div>
                <div className="thin-scrollbar border-neutral-2 bg-neutral-1 flex h-[200px] flex-col gap-2.5 overflow-y-auto rounded-xl border p-3">
                  {isLoading ? (
                    <div className="text-body-small text-gray-40 flex h-full items-center justify-center">
                      목록을 불러오는 중...
                    </div>
                  ) : items.length === 0 ? (
                    <div className="text-body-small text-gray-40 flex h-full items-center justify-center">
                      항목이 없습니다.
                    </div>
                  ) : (
                    items.map((item) => {
                      const checked = selectedItems.has(item.id);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => toggleItem(item.id)}
                          className="flex w-full cursor-pointer items-center gap-3"
                        >
                          <span className="text-body-small text-gray-60 min-w-0 flex-1 truncate text-left">
                            {item.name}
                          </span>
                          {checked ? (
                            <CheckboxChecked className="size-6 shrink-0 text-blue-50" />
                          ) : (
                            <CheckboxUnchecked className="text-gray-30 size-6 shrink-0" />
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-1 flex h-9 w-full items-start justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button variant="capsule-solid-primary" size="md" disabled={isSubmitDisabled} onClick={handleSubmit}>
            임베딩하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmbeddingModal;
