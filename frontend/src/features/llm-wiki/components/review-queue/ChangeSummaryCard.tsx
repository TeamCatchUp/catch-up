import IconAi from '@/public/icons/icon/ai.svg';

interface ChangeSummaryCardProps {
  changeCount: number;
  /** "영향 문서 N건" — 백엔드 대응 값이 없어 표시 문자열째 받는다 */
  affectedDocumentsLabel: string;
  body: string;
}

/** 제안 상세 상단의 AI 변경 요약 카드("이렇게 바뀌었어요"). */
export default function ChangeSummaryCard({ changeCount, affectedDocumentsLabel, body }: ChangeSummaryCardProps) {
  return (
    <section className="border-line-normal-neutral flex flex-col gap-3 rounded-xl border px-5 py-4">
      <div className="flex items-center gap-3">
        <IconAi aria-hidden className="text-icon-normal-normal size-6 shrink-0" />
        <h3 className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">이렇게 바뀌었어요</h3>
        <div className="text-body-xsmall text-text-primary-assistive flex shrink-0 items-center gap-1.5">
          <span>변경 {changeCount}건</span>
          <span aria-hidden className="bg-fill-primary-normal-interaction-inactive size-1 rounded-full" />
          <span>{affectedDocumentsLabel}</span>
        </div>
      </div>
      <p className="text-body-small text-text-normal-neutral">{body}</p>
    </section>
  );
}
