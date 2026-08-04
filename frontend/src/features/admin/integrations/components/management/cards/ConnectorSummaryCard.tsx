import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';

interface ConnectorSummaryCardProps {
  connected: boolean;
  /** 임베딩 데이터 범위 문자열. 없으면 미연동 문구를 보여준다 */
  dataRange: string | null;
}

/**
 * 커넥터 상세 요약 — 연동 상태 + 임베딩 데이터 범위 2행.
 * Figma `17071:111589` — 716×104, 행 각 52, 라벨 x16, 값 우측 정렬.
 *
 * 구 레이아웃의 카드 2개(`ConnectionStatusCard` + `DataRangeCard`)를 대체했고,
 * 그 둘은 2026-08-03에 삭제됐다. 구 카드에 있던 "보안 관련 설명 / 원문 보기" 행은
 * 신규 디자인에 없고, 미연동 시의 "연동하기" 버튼은 상세 헤더로 승격됐다.
 *
 * 미연동·범위 없음 문구는 Figma에 없어 현행 코드에서 승계했다.
 */
export default function ConnectorSummaryCard({ connected, dataRange }: ConnectorSummaryCardProps) {
  return (
    <dl className="border-line-normal-neutral divide-line-normal-neutral bg-fill-normal-strong divide-y overflow-hidden rounded-xl border">
      <div className="flex h-13 items-center justify-between gap-8 px-4">
        <dt className="text-body-small text-text-normal-normal min-w-0 truncate">연동 상태</dt>
        <dd className="flex shrink-0 items-center gap-2 px-1.5 py-1">
          {connected ? (
            <>
              <IconCloudCheckFilled className="text-icon-primary-assistive size-5 shrink-0" />
              <span className="text-body-small text-text-primary-assistive">연동됨</span>
            </>
          ) : (
            <>
              <IconCloudOff className="text-icon-normal-assistive size-5 shrink-0" />
              <span className="text-body-small text-text-normal-alternative">연동 안됨</span>
            </>
          )}
        </dd>
      </div>

      <div className="flex h-13 items-center justify-between gap-8 px-4">
        {/* 라벨이 먼저 줄고, 날짜는 한 줄을 유지한다 — 좁은 폭에서 값이 두 줄로 접히면 행 52가 무너진다 */}
        <dt className="text-body-small text-text-normal-normal min-w-0 truncate">임베딩 데이터 범위</dt>
        <dd
          className={
            dataRange
              ? 'text-body-small text-text-normal-alternative shrink-0 px-1.5 whitespace-nowrap'
              : 'text-body-small text-text-normal-assistive shrink-0 whitespace-nowrap'
          }
        >
          {dataRange ?? '연동되지 않았습니다.'}
        </dd>
      </div>
    </dl>
  );
}
