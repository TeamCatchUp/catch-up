import type { ComponentType, SVGProps } from 'react';

interface MappingStatCardProps {
  /** 커넥터 브랜드 로고 (`CONNECTOR_LOGOS`) */
  Logo: ComponentType<SVGProps<SVGSVGElement>>;
  name: string;
  /** 완료율(%). 정수로 반올림해 넘긴다 */
  percent: number;
  /** "65/100" 형태의 건수 */
  countLabel: string;
}

/**
 * 계정 등록 상태 카드 1장.
 * Figma `17300:80305` — p 20, gap 20, 로고칩 48(p 8, radius 12, fill/normal/strong,
 * 로고 28), 이름·완료율 heading-small, 건수 Tag(fill/primary/normal/neutral,
 * px 6 py 2, radius 6, 13px text/primary/normal).
 * 두 번째 카드부터 왼쪽 구분선(`line/normal/neutral`)이 붙는다.
 *
 * **표시 전용이다.** 누를 수 없고 상태 변형도 없다 — Figma 카드 5장은 전부
 * FRAME 이라 variant 자체가 없고, 전체 화면과 채널톡 필터 화면에서 fill 이
 * 똑같이 비어 있다. 표를 거르는 건 필터 칩이 한다(사용자 결정 2026-08-04).
 *
 * 카드 폭 208은 행 1040의 5등분이라 박지 않는다. basis 180 은 로고칩 48 +
 * gap 20 + 이름·완료율이 겹치지 않는 하한이고, 넘치면 행이 줄바꿈한다
 * (1024 에서 균등 압축하면 130px 까지 줄어 내용이 겹쳤다 — 실측).
 */
export default function MappingStatCard({ Logo, name, percent, countLabel }: MappingStatCardProps) {
  return (
    <div className="border-line-normal-neutral flex min-w-0 flex-1 basis-45 items-center gap-5 border-l p-5 first:border-l-0">
      <span className="bg-fill-normal-strong flex size-12 shrink-0 items-center justify-center rounded-xl p-2">
        <Logo className="size-7" />
      </span>
      <span className="flex min-w-0 flex-col gap-1">
        <span className="text-heading-small text-text-normal-normal truncate">{name}</span>
        <span className="flex items-center gap-2">
          <span className="text-heading-small text-text-normal-neutral">{percent}%</span>
          <span className="bg-fill-primary-normal-neutral text-body-xsmall text-text-primary-normal rounded-md2 px-1.5 py-0.5 whitespace-nowrap">
            {countLabel}
          </span>
        </span>
      </span>
    </div>
  );
}
