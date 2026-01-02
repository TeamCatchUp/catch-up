import CloudCheck from '/public/icons/icon/cloud_check.svg';
import JiraLogo from '/public/icons/logo/Jira.svg';
import ConfluenceLogo from '/public/icons/logo/Counfluence.svg';
import GithubLogo from '/public/icons/logo/GitHub.svg';
import SlackLogo from '/public/icons/logo/Slack.svg';
import ArrowOutward from '/public/icons/icon/arrow_outward.svg';

const cardData = [
  {
    image: JiraLogo,
    title: 'Jira 연동하기',
    description: '팀이 진행한 모든 업무가 한 곳에 정리됩니다.',
  },
  {
    image: GithubLogo,
    title: 'Github 연동하기',
    description: '모든 작업 파일이 업무에 맞춰서 정리됩니다.',
  },
  {
    image: ConfluenceLogo,
    title: 'Confluence 연동하기',
    description: '모든 페이지가 업무에 맞추어 연결됩니다.',
  },
  {
    image: SlackLogo,
    title: 'Slack 연동하기',
    description: '팀의 모든 논의가 업무에 맞춰서 정리됩니다.',
  },
];

const LinkTool = () => {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <div className="border-neutral-3 bg-blue-1 rounded-lg border-[0.5px] p-1.5">
          <CloudCheck className="h-5 w-5 text-blue-50" />
        </div>
        <div className="text-heading-large text-gray-80">협업 툴 연동하기</div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {cardData.map((card, idx) => {
          const CardImg = card.image;
          return (
            <div
              key={idx}
              className="border-neutral-3 flex h-[85px] w-[549px] items-center justify-between rounded-2xl border bg-white px-5 py-4"
            >
              <div className="flex items-center gap-4">
                <div className="border-neutral-5 shadow-button flex h-10 w-10 items-center justify-center rounded-xl border">
                  <CardImg className="h-7 w-7" />
                </div>
                <div>
                  <div className="text-heading-large text-gray-70">{card.title}</div>
                  <div className="text-body-xsmall text-gray-50">{card.description}</div>
                </div>
              </div>

              <button className="bg-neutral-1 border-neutral-3 flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl border p-1.5">
                <ArrowOutward className="text-gray-70 h-6" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LinkTool;
