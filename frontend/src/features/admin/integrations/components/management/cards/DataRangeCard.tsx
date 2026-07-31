import { cn } from '@/shared/utils/cn';

interface DataRangeCardProps {
  connected: boolean;
  dataRange: string;
  /** 미연결 시 좌측 정렬할지. 채널톡 true, 일반 false — 현행 렌더 보존용. */
  alignStartWhenDisconnected: boolean;
}

/**
 * "연동된 데이터 범위" 카드.
 * 두 패널에 복제돼 있던 것을 한 벌로 합쳤다. 정렬 규칙 차이는 prop으로 재현한다.
 */
export default function DataRangeCard({ connected, dataRange, alignStartWhenDisconnected }: DataRangeCardProps) {
  const centered = connected || !alignStartWhenDisconnected;

  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-text-normal-neutral">연동된 데이터 범위</h3>
      <div
        className={cn(
          'border-line-normal-assistive bg-fill-normal-strong text-body-small flex items-center overflow-hidden rounded-xl border px-4 py-3',
          connected ? 'text-text-normal-normal' : 'text-text-normal-assistive',
          centered && 'justify-center',
        )}
      >
        <span className="truncate">{connected ? dataRange : '연동되지 않았습니다.'}</span>
      </div>
    </div>
  );
}
