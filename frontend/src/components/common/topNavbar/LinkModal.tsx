import JiraLogo from '/public/icons/logo/Jira.svg';
import ConfluenceLogo from '/public/icons/logo/Counfluence.svg';
import GithubLogo from '/public/icons/logo/GitHub.svg';
import SlackLogo from '/public/icons/logo/Slack.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';

const services = [
  { key: 'Jira', label: 'Jira', Icon: JiraLogo },
  { key: 'Confluence', label: 'Confluence', Icon: ConfluenceLogo },
  { key: 'Github', label: 'Github', Icon: GithubLogo },
  { key: 'Slack', label: 'Slack', Icon: SlackLogo },
] as const;

type Props = {
  linked: Record<string, boolean>;
  onToggle: React.Dispatch<React.SetStateAction<any>>;
};

const LinkModal = ({ linked, onToggle }: Props) => {
  return (
    <div className="shadow-dropdown-menu border-neutral-4 h-45.5 w-63 gap-0.5 rounded-2xl border bg-white px-1.5 py-2">
      {services.map(({ key, label, Icon }) => (
        <button
          key={key}
          onClick={() =>
            onToggle((prev: any) => ({
              ...prev,
              [key]: !prev[key],
            }))
          }
          className="flex h-10 w-59.5 cursor-pointer items-center justify-between p-2"
        >
          <div className="flex gap-2">
            <Icon className="h-5 w-5" />
            <span className="text-gray-80">{label}</span>
          </div>
          <div className="flex items-center">
            <span className="text-body-xsmall text-gray-50">{linked[key] ? '연동' : '미연동'}</span>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>
      ))}
    </div>
  );
};

export default LinkModal;
