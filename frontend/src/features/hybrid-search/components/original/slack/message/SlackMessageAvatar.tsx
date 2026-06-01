import Image from 'next/image';

import type { SlackAvatarSource } from '@/features/hybrid-search/types/slackOriginalModel';
import ProfileIcon from '@/public/icons/icon/profile.svg';
import SlackBotBadgeIcon from '@/public/icons/icon/slack_bot_badge.svg';
import SlackBotFallbackIcon from '@/public/icons/icon/slack_bot_fallback.svg';
import { cn } from '@/shared/utils/cn';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface SlackMessageAvatarProps {
  name: string;
  avatarUrl: string | null;
  avatarSource: SlackAvatarSource;
  kind: 'user' | 'bot' | 'unknown';
}

export default function SlackMessageAvatar({
  name,
  avatarUrl,
  avatarSource,
  kind,
}: SlackMessageAvatarProps) {
  const isBot = kind === 'bot';
  const safeAvatarUrl = avatarUrl && isSafeUrl(avatarUrl) ? avatarUrl : null;
  const showBotBadge = isBot && !(safeAvatarUrl && avatarSource === 'message_icons');

  return (
    <span
      className={cn(
        'relative flex shrink-0 items-center justify-center rounded-lg',
        isBot
          ? cn('size-9 p-1', !safeAvatarUrl && 'bg-fill-primary')
          : 'size-8 overflow-hidden',
      )}
    >
      {safeAvatarUrl ? (
        <Image
          src={safeAvatarUrl}
          alt=""
          width={isBot ? 28 : 32}
          height={isBot ? 28 : 32}
          className={cn(isBot ? 'size-7 rounded-md' : 'size-8 rounded-lg', 'object-cover')}
          unoptimized
        />
      ) : isBot ? (
        <SlackBotFallbackIcon aria-label={name} className="size-6" />
      ) : (
        <ProfileIcon aria-label={name} className="size-8 rounded-lg" />
      )}
      {showBotBadge && (
        <span className="bg-fill-normal absolute -top-1 left-5.75 flex size-3.25 items-center justify-center rounded-full p-0.5">
          <SlackBotBadgeIcon aria-hidden className="size-2.75" />
        </span>
      )}
    </span>
  );
}
