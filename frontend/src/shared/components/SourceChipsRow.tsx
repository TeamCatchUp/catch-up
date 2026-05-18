'use client';

// 입력 박스에 노출되는 소스 chips. 문서 탐색·AI 검색·채팅에서 공용으로 재사용.
// controlled 컴포넌트로 selectedSources/onToggle을 부모가 관리.

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

interface SourceItem {
  value: DocsSource;
  label: string;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

interface SourceChipsRowProps {
  className?: string;
  selectedSources: DocsSource[];
  onToggle: (next: DocsSource[]) => void;
}

const SOURCES: ReadonlyArray<SourceItem> = [
  { value: 'confluence', label: 'Confluence', Icon: Confluence },
  { value: 'jira', label: 'Jira', Icon: Jira },
  { value: 'slack', label: 'Slack', Icon: Slack },
  { value: 'github', label: 'Github', Icon: GitHub },
  { value: 'channel_talk', label: '채널톡', Icon: ChannelTalk },
];

export default function SourceChipsRow({ className, selectedSources, onToggle }: SourceChipsRowProps) {
  const toggle = (value: DocsSource) => {
    const next = selectedSources.includes(value)
      ? selectedSources.filter((v) => v !== value)
      : [...selectedSources, value];
    onToggle(next);
  };

  return (
    <div className={cn('flex items-center justify-center gap-2.5', className)}>
      {SOURCES.map((s) => (
        <SearchOptionButton
          key={s.value}
          Icon={s.Icon}
          label={s.label}
          selected={selectedSources.includes(s.value)}
          onClick={() => toggle(s.value)}
          iconClassName={s.value === 'channel_talk' ? 'h-4 w-4' : undefined}
        />
      ))}
    </div>
  );
}
