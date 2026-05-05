import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import Github from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';

export type SourceType = 'jira' | 'github' | 'slack' | 'confluence' | 'channel_talk';

const SOURCE_LOGO: Record<SourceType, React.FC<React.SVGProps<SVGElement>>> = {
  github: Github,
  jira: Jira,
  slack: Slack,
  confluence: Confluence,
  channel_talk: ChannelTalk,
};

export default function SourceBadge({ n, sourceType }: { n: string; sourceType: SourceType }) {
  const Logo = SOURCE_LOGO[sourceType];

  return (
    <span className="bg-fill-strong border-edge-assistive inline-flex items-center justify-center gap-1 rounded-full border px-1.5 py-1 align-middle whitespace-nowrap">
      <Logo className="h-5 w-5 shrink-0" />
      <span className="text-body-xsmall text-content-strong">{n}</span>
    </span>
  );
}
