import IconClockPending from '@/public/icons/icon/clock_pending.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';

import type { EmbeddingProgressItem, SyncConnector } from '../../../types/syncModel';
import { RESOURCE_ICONS } from '../../../utils/embeddingUtils';

interface EmbeddingActiveCardProps {
  items: EmbeddingProgressItem[];
  connector: SyncConnector;
}

const EmbeddingActiveCard = ({ items, connector }: EmbeddingActiveCardProps) => {
  const ResourceIcon = RESOURCE_ICONS[connector];

  return (
    <div className="border-edge-assistive bg-fill-normal flex max-h-70 flex-col gap-1 overflow-clip rounded-2xl border py-4">
      {/* 헤더 */}
      <div className="flex items-center gap-1 px-4">
        <span className="text-body-xsmall text-content-primary">임베딩 진행 중</span>
        <IconRotate className="text-content-primary size-4.5" />
      </div>

      {/* 아이템 리스트 */}
      <div className="thin-scrollbar flex flex-col overflow-y-auto">
        {items.map((item) => (
          <div key={item.targetId} className="border-edge-assistive flex h-14 shrink-0 items-center gap-4 border-b px-4 last:border-b-0">
            <div className="border-edge-normal bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
              <ResourceIcon className="size-5" />
            </div>
            <span className="text-body-small text-content-normal flex-1 truncate">{item.displayName}</span>
            {item.status === 'pending' ? (
              <IconClockPending className="text-status-cautionary size-6" />
            ) : (
              <IconRotate className="text-content-primary size-6 animate-spin" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default EmbeddingActiveCard;
