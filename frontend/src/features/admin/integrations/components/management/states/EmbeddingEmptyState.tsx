import Image from 'next/image';

/**
 * 임베딩된 대상이 하나도 없을 때 표 자리에 들어가는 안내.
 * Figma `17306:82275` — 일러스트 258×70, 상단 여백 120, gap 24.
 *
 * 문구는 상태 감사가 `UNKNOWN(구현 승계)`으로 오판정했던 항목이다.
 * Figma에 프레임이 있고, 현행 "연동된 항목이 없습니다."가 아니라 이 문구가 승인본이다.
 */
export default function EmbeddingEmptyState() {
  return (
    <div className="flex flex-col items-center gap-6 py-30">
      <Image
        src="/image/status/empty-embedding-light.png"
        alt=""
        width={258}
        height={70}
        className="h-auto w-64.5"
      />
      <p className="text-body-small text-text-normal-assistive">임베딩한 채널이 없습니다</p>
    </div>
  );
}
