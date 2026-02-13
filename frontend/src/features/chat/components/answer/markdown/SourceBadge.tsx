import Github from '/public/icons/logo/GitHub.svg';
import Jira from '/public/icons/logo/Jira.svg';
import Slack from '/public/icons/logo/Slack.svg';

export type SourceType = 'jira' | 'github' | 'slack';

const SOURCE_LOGO: Record<SourceType, React.FC<React.SVGProps<SVGElement>>> = {
  github: Github,
  jira: Jira,
  slack: Slack,
};

const SourceBadge = ({ n, sourceType }: { n: string; sourceType: SourceType }) => {
  const Logo = SOURCE_LOGO[sourceType];

  return (
    <span className="bg-neutral-2 relative top-0.5 mr-px inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 whitespace-nowrap">
      <Logo className="h-4 w-4 shrink-0" />
      <span className="text-body-xsmall text-gray-80">{n}</span>
    </span>
  );
};

export default SourceBadge;
