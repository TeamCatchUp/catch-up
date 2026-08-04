'use client';

import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import IconTodo from '@/public/icons/icon/todo.svg';
import { Button } from '@/shared/components/ui/button';

interface MappingActionsBarProps {
  onSyncSso: () => void;
  onSyncDb: () => void;
  onOpenCsvUpload: () => void;
  onEdit: () => void;
  /** 동기화 진행중 — 두 동기화 버튼 비활성 (구현 승계: 버튼 disabled) */
  isSyncing?: boolean;
}

/**
 * 계정 매핑 상태 액션 바 — 동기화 2종 + CSV 등록 + 수정하기 버튼 묶음.
 * 동기화·CSV 묶음과 수정하기 사이는 세로 divider로 구분한다.
 */
export default function MappingActionsBar({
  onSyncSso,
  onSyncDb,
  onOpenCsvUpload,
  onEdit,
  isSyncing = false,
}: MappingActionsBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="box-outline-gray" size="md" onClick={onSyncSso} disabled={isSyncing}>
        SSO User 동기화
      </Button>
      <Button variant="box-outline-gray" size="md" onClick={onSyncDb} disabled={isSyncing}>
        이용자 DB 동기화
      </Button>
      <Button variant="box-outline-gray" size="md" onClick={onOpenCsvUpload}>
        <IconTodo className="size-5" />
        CSV 일괄 등록
      </Button>
      <span aria-hidden="true" className="bg-line-normal-neutral mx-2 h-6 w-px shrink-0" />
      <Button variant="box-outline-gray" size="md" onClick={onEdit}>
        <IconEditPencil className="size-4" />
        수정하기
      </Button>
    </div>
  );
}
