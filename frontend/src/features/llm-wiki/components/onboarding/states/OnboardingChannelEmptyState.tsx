import IconEmptyChannel from '@/public/icons/icon/empty.svg';

/** 아직 고른 채널이 없을 때 표 머리글 아래에 들어가는 안내. 표 셸과 머리글은 그대로 남는다. */
export default function OnboardingChannelEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-20">
      <IconEmptyChannel aria-hidden className="h-[69.9px] w-[258px] shrink-0" />
      <p className="text-label-xsmall text-text-normal-assistive text-center">선택한 채널톡 채널이 없습니다</p>
    </div>
  );
}
