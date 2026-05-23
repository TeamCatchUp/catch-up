'use client';

// 검색 시 선택된 툴 indicator. URL 의 ?tools= 비어있으면(필터 없음) 렌더 자체 안 함.
// 캐노니컬 순서: Confluence / Jira / Slack / GitHub / 채널톡 (Figma 14084-65597).

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';

import type { ToolFilter } from '../types/hybridSearchApi';

interface SearchToolLabelProps {
  tools: ToolFilter[];
}

const TOOL_LOGO: Record<ToolFilter, React.FC<React.SVGProps<SVGSVGElement>>> = {
  confluence: Confluence,
  jira: Jira,
  slack: Slack,
  github: GitHub,
  channel_talk: ChannelTalk,
};

// 표시 순서는 사용자가 토글한 순서와 무관하게 캐노니컬로 고정.
const CANONICAL_ORDER: ToolFilter[] = ['confluence', 'jira', 'slack', 'github', 'channel_talk'];

export default function SearchToolLabel({ tools }: SearchToolLabelProps) {
  if (tools.length === 0) return null;

  const selected = new Set(tools);
  const ordered = CANONICAL_ORDER.filter((t) => selected.has(t));

  return (
    <div className="bg-fill-normal border-edge-assistive flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-1">
      {ordered.map((tool) => {
        const Logo = TOOL_LOGO[tool];
        return <Logo key={tool} className="h-4.5 w-4.5" />;
      })}
    </div>
  );
}
