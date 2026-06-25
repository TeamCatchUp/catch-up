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
    <span className="bg-fill-normal-strong border-line-normal-assistive inline-flex items-center justify-center gap-1 rounded-full border px-1.5 py-1 align-middle whitespace-nowrap">
      <Logo className={`${sourceType === 'channel_talk' ? 'h-4 w-4' : 'h-5 w-5'} shrink-0`} />
      <span className="text-body-xsmall text-text-normal-strong">{n}</span>
    </span>
  );
}
