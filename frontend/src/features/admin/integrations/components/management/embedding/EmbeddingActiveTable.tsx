import type { IntegrationService } from '../../../types/integrationModel';
import EmbeddingHistoryRow from './EmbeddingHistoryRow';
import EmbeddingTableHeader from './EmbeddingTableHeader';

export interface EmbeddingActiveItem {
  id: string;
  target: string;
}

interface EmbeddingActiveTableProps {
  service: IntegrationService;
  items: readonly EmbeddingActiveItem[];
}

/**
 * 진행중인 임베딩 목록 — 히스토리와 같은 열을 쓴다. 두 표가 같은 패널에
 * 위아래로 쌓이므로 열 x가 같아야 한다. 그래서 폭을 내용에 맡기지 않는다.
 * 진행중이 없으면 섹션 자체를 렌더하지 않는다(Figma에 빈 상태가 없다).
 */
export default function EmbeddingActiveTable({ service, items }: EmbeddingActiveTableProps) {
  if (items.length === 0) return null;

  return (
    // 고정 열 합조차 안 되는 좁은 슬롯에서만 스크롤로 흘린다
    <div className="overflow-x-auto">
      <table role="table" className="block w-full min-w-fit">
        <EmbeddingTableHeader />
        <tbody role="rowgroup" className="block">
          {items.map((item) => (
            <EmbeddingHistoryRow
              key={item.id}
              service={service}
              target={item.target}
              status="running"
              executedAt={null}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
