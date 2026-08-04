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
 * 계정 매핑 상태 액션 바.
 * Figma `17379:78312` 우측 — Box Button Outline(Gray) medium ×4
 * (`box-outline-gray`), CSV·수정하기는 좌측 아이콘, 사이에 세로 divider.
 * 라벨은 Figma 인스턴스 실측: SSO User 동기화 / 이용자 DB 동기화 /
 * CSV 일괄 등록 / 수정하기.
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
