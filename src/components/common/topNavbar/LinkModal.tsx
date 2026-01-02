import JiraLogo from '/public/icons/logo/Jira.svg';
import ConfluenceLogo from 'public/icons/logo/Counfluence.svg';
import GithubLogo from '/public/icons/logo/Github.svg';
import SlackLogo from '/public/icons/logo/Slack.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';

const LinkModal = () => {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="link-modal-title"
      className="shadow-dropdown-menu border-neutral-4 h-[182px] w-[281px] gap-0.5 rounded-2xl border bg-white px-1.5 py-2"
    >
      <h2 id="link-model-title" className="sr-only">
        외부 서비스 연결
      </h2>

      <button className="flex h-10 w-[269px] cursor-pointer items-center justify-between p-2">
        <div className="flex gap-2">
          <JiraLogo className="h-5 w-5" aria-hidden="true" />
          <span className="text-gray-80">Jira</span>
        </div>
        <div className="flex items-center">
          <span className="text-body-xsmall text-gray-50">미연동</span>
          <ArrowRight className="text-gray-30 h-6 w-6" />
        </div>
      </button>

      <button className="flex h-10 w-[269px] cursor-pointer items-center justify-between p-2">
        <div className="flex gap-2">
          <ConfluenceLogo className="h-5 w-5" aria-hidden="true" />
          <span className="text-gray-80">Confluence</span>
        </div>
        <div className="flex items-center">
          <span className="text-body-xsmall text-gray-50">연동</span>
          <ArrowRight className="text-gray-30 h-6 w-6" />
        </div>
      </button>

      <button className="flex h-10 w-[269px] cursor-pointer items-center justify-between p-2">
        <div className="flex gap-2">
          <GithubLogo className="h-5.5 w-6" aria-hidden="true" />
          <span className="text-gray-80 relative top-px right-1">Github</span>
        </div>
        <div className="flex items-center">
          <span className="text-body-xsmall text-gray-50">미연동</span>
          <ArrowRight className="text-gray-30 h-6 w-6" />
        </div>
      </button>

      <button className="flex h-10 w-[269px] cursor-pointer items-center justify-between p-2">
        <div className="flex gap-2">
          <SlackLogo className="h-5.5 w-5.5" aria-hidden="true" />
          <span className="text-gray-80 relative top-px right-0.5">Slack</span>
        </div>
        <div className="flex items-center">
          <span className="text-body-xsmall text-gray-50">미연동</span>
          <ArrowRight className="text-gray-30 h-6 w-6" />
        </div>
      </button>
    </div>
  );
};

export default LinkModal;
