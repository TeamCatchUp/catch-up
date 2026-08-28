import IconAiFilled from '@/public/icons/icon/ai_filled.svg';

/** 시안의 AI 오버레이 그라데이션 2겹. 색 스탑은 모드 토큰이고 기하만 컴포넌트 로컬이다 */
const AI_GRADIENT =
  'radial-gradient(5.08% 137.64% at 0.69% 7.96%, var(--fill-overlay-gradient-ai-start) 0%, var(--fill-overlay-gradient-ai-mid) 100%), ' +
  'radial-gradient(90.98% 94.18% at 47.32% 50.44%, var(--fill-overlay-gradient-ai-core) 0%, var(--fill-overlay-gradient-ai-mid) 51.01%, var(--fill-overlay-gradient-ai-end) 90.17%)';

interface ChangeSummaryCardProps {
  changeCount: number;
  /** "영향 문서 N건" — 백엔드 대응 값이 없어 표시 문자열째 받고, 없으면 자리째 빠진다 */
  affectedDocumentsLabel?: string;
  body: string;
}

/** 제안 상세 상단의 AI 변경 요약 카드("이렇게 바뀌었어요"). */
export default function ChangeSummaryCard({ changeCount, affectedDocumentsLabel, body }: ChangeSummaryCardProps) {
  return (
    <section
      className="border-line-normal-neutral bg-fill-overlay-background-elevated flex flex-col gap-3 rounded-xl border px-5 py-4"
      style={{ backgroundImage: AI_GRADIENT }}
    >
      <div className="flex items-center gap-1.5">
        <IconAiFilled aria-hidden className="text-icon-normal-alternative size-5.5 shrink-0" />
        <h3 className="text-body-small text-text-normal-alternative min-w-0 flex-1 truncate">이렇게 바뀌었어요</h3>
        <div className="text-body-xsmall text-text-primary-assistive flex shrink-0 items-center gap-1.5">
          <span>변경 {changeCount}건</span>
          {affectedDocumentsLabel && (
            <>
              <span aria-hidden className="bg-fill-primary-normal-interaction-hover-assistive size-1 rounded-full" />
              <span>{affectedDocumentsLabel}</span>
            </>
          )}
        </div>
      </div>
      <p className="text-heading-small text-text-normal-neutral">{body}</p>
    </section>
  );
}
