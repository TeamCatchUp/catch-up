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
 * 진행중인 임베딩 목록.
 * Figma `17125:114635` — 히스토리와 같은 4열 헤더를 쓴다.
 * 진행중이 없으면 섹션 자체를 렌더하지 않는다(Figma에 빈 상태가 없다).
 */
export default function EmbeddingActiveTable({ service, items }: EmbeddingActiveTableProps) {
  if (items.length === 0) return null;

  return (
    // 폭을 박지 않고, 내용 최소폭조차 안 되는 슬롯에서만 스크롤로 흘린다
    <div className="overflow-x-auto">
      <table className="w-full">
        <EmbeddingTableHeader />
        <tbody>
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
