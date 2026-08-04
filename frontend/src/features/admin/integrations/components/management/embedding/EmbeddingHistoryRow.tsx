import IconReset from '@/public/icons/icon/reset.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { cn } from '@/shared/utils/cn';

import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';
import { formatFailureCount } from '../../../utils/formatFailureCount';
import { EMBEDDING_ROW_GRID } from './embeddingTableGrid';

export type EmbeddingRowStatus = 'running' | 'success' | 'failed';

interface EmbeddingHistoryRowProps {
  service: IntegrationService;
  target: string;
  status: EmbeddingRowStatus;
  /** 진행중이면 null — 시각 칸에 선이 들어간다 */
  executedAt: string | null;
  failureCount?: number;
  onRetry?: () => void;
}

function StatusBadge({ status, failureCount = 0 }: Pick<EmbeddingHistoryRowProps, 'status' | 'failureCount'>) {
  if (status === 'running') {
    return (
      <span className="bg-accent-light-blue-lighten inline-flex items-center gap-2 rounded-lg px-2 py-1">
        <span className="text-body-xsmall text-text-primary-normal">진행중</span>
        <IconRotate className="text-icon-primary-normal size-4.5" />
      </span>
    );
  }

  if (status === 'success') {
    return (
      <span className="bg-accent-green-lighten inline-flex items-center rounded-lg px-2 py-1">
        <span className="text-body-xsmall text-status-positive">성공</span>
      </span>
    );
  }

  return (
    <span className="bg-accent-red-lighten inline-flex items-center gap-2 rounded-lg px-2 py-1">
      <span className="text-body-xsmall text-status-destructive">실패</span>
      <span aria-hidden="true" className="bg-accent-red-default h-2.5 w-px shrink-0" />
      <span className="text-body-xsmall text-status-destructive">{formatFailureCount(failureCount)}</span>
    </span>
  );
}

/**
 * 임베딩 히스토리 한 행. `<tr>`이라 `<tbody>` 안에서만 쓴다.
 * 행 높이는 아이콘 버튼이 만드는 값이라 고정하지 않고 `min-h`로 둔다.
 *
 * 폭·간격은 {@link EMBEDDING_ROW_GRID}가 정한다 — 셀에 padding을 주지 않는다.
 * 진행중의 시각 칸은 텍스트가 아니라 회색 선이다. 성공 행도 액션 슬롯을
 * 비운 채 유지해 열 정렬을 맞춘다.
 */
export default function EmbeddingHistoryRow({
  service,
  target,
  status,
  executedAt,
  failureCount = 0,
  onRetry,
}: EmbeddingHistoryRowProps) {
  const Logo = CONNECTOR_LOGOS[service];

  return (
    <tr role="row" className={cn(EMBEDDING_ROW_GRID, 'min-h-11.5')}>
      <td role="cell" className="flex min-w-0 items-center gap-2.5">
        <Logo className="size-5 shrink-0" />
        <span className="text-body-small text-text-normal-neutral truncate">{target}</span>
      </td>

      <td role="cell" className="min-w-0">
        <StatusBadge status={status} failureCount={failureCount} />
      </td>

      <td role="cell" className="min-w-0 truncate">
        {executedAt ? (
          <span className="text-body-small text-text-normal-assistive">{executedAt}</span>
        ) : (
          <span aria-hidden="true" className="bg-line-normal-neutral block h-0.75 w-4.5 rounded-full" />
        )}
      </td>

      {/* 아이콘 버튼을 액션 칸의 오른쪽 끝에 붙인다 */}
      <td role="cell" className="flex justify-end">
        {status === 'failed' && onRetry && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="icon-outline-gray" size="sm" onClick={onRetry} aria-label="임베딩 재시도">
                <IconReset className="size-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>임베딩 재시도</TooltipContent>
          </Tooltip>
        )}
      </td>
    </tr>
  );
}
