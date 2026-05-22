// 채팅 타임라인의 날짜 구분선. 좌우 라인 + 중앙 날짜 캡슐.

interface DateIndicatorProps {
  date: string;
}

// ISO datetime → MM.DD. 파싱 불가하면 빈 문자열.
function formatDateLabel(date: string): string {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return '';

  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const day = String(parsed.getDate()).padStart(2, '0');
  return `${month}.${day}`;
}

export default function DateIndicator({ date }: DateIndicatorProps) {
  const label = formatDateLabel(date);
  if (!label) return null;

  return (
    <div className="flex w-full items-center gap-2">
      <span aria-hidden className="bg-edge-neutral h-px flex-1" />
      <span className="bg-fill-normal border-edge-neutral text-body-xsmall text-content-alternative shrink-0 rounded-full border px-3 py-1 font-medium">
        {label}
      </span>
      <span aria-hidden className="bg-edge-neutral h-px flex-1" />
    </div>
  );
}
