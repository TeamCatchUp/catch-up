/**
 * 아직 고른 채널이 없을 때 표 자리에 들어가는 안내.
 * 표가 "선택 결과"임이 확정돼(8/14) 문구를 그에 맞췄다 — 카피는 여전히 승인 전이다.
 */
export default function OnboardingChannelEmptyState() {
  return (
    <div className="border-line-normal-neutral flex items-center justify-center rounded-xl border px-6 py-16">
      <p className="text-body-small text-text-normal-assistive">아직 선택한 채널이 없습니다</p>
    </div>
  );
}
