/**
 * 선택할 수 있는 채널이 하나도 없을 때 표 자리에 들어가는 안내.
 * 사실만 적고 연동·생성 경로는 안내하지 않는다 — 그 동선은 아직 정해지지 않았다.
 */
export default function OnboardingChannelEmptyState() {
  return (
    <div className="border-line-normal-neutral flex items-center justify-center rounded-xl border px-6 py-16">
      <p className="text-body-small text-text-normal-assistive">선택할 수 있는 채널이 없습니다</p>
    </div>
  );
}
