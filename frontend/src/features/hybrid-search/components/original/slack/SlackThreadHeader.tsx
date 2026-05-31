import GroupIcon from '@/public/icons/icon/group.svg';
import TagIcon from '@/public/icons/icon/tag.svg';

interface SlackThreadHeaderProps {
  channelName: string;
  participantNames: string[];
}

export default function SlackThreadHeader({ channelName, participantNames }: SlackThreadHeaderProps) {
  const participants = participantNames.length > 0 ? participantNames.join(', ') : '참여자 정보 없음';

  return (
    <div className="bg-fill-strong border-edge-neutral flex w-99.75 max-w-full shrink-0 flex-col items-start gap-3 overflow-hidden rounded-xl border px-5 py-4">
      <div className="flex h-7 w-full items-center gap-4">
        <span className="border-edge-strong flex shrink-0 items-center overflow-hidden rounded-lg border p-0.5">
          <TagIcon className="text-icon-neutral size-5.5" aria-hidden />
        </span>
        <span className="text-heading-small text-content-normal min-w-0 flex-1 truncate font-semibold">
          {channelName}
        </span>
      </div>
      <div className="flex h-7 w-full items-center gap-4">
        <GroupIcon className="text-icon-neutral size-5.5 shrink-0" aria-hidden />
        <span className="text-body-small text-content-neutral min-w-0 flex-1 truncate font-medium">{participants}</span>
      </div>
    </div>
  );
}
