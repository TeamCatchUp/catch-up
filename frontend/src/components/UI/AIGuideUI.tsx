import IconX from '@/public/icons/icon/TextfiledDelete.svg';
import IconHelp from '@/public/icons/icon/helpWhite.svg';
import JiraGuide from '@/public/image/jiraGuidJpg.jpg';
import GitGuide from '@/public/image/gitGuidejpg.jpg';
import Image from 'next/image';

interface GuideCardProps {
  onClose: () => void;
}

export function JiraGuideCard({ onClose }: GuideCardProps) {
  return (
    <div className="border-neutral-3 shadow-card flex w-190 flex-col items-start gap-8 rounded-3xl border bg-white p-5">
      <div className="flex flex-col items-start gap-5 self-stretch">
        <div className="flex items-center justify-between self-stretch">
          <div className="bg-gray-70 flex items-center justify-center gap-2 rounded-[10px] px-2 py-1 text-white">
            <IconHelp className="h-6 w-6 text-white" />
            <div className="text-heading-small">Jira 스페이스 선택 가이드</div>
          </div>
          <button onClick={onClose} className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
            <IconX />
          </button>
        </div>
        <div className="flex flex-col items-start gap-1.5 self-stretch">
          <div className="text-heading-medium text-gray-90">
            캐치스턴트 AI에게 <span className="text-blue-55">참고할 범위</span>를 알려주세요
          </div>
          <div className="text-body-small text-gray-70 self-stretch">
            Project나 Ticket을 지정하면 의사결정 흐름과 변경 이력을 기준 더 정확한 답변을 받을 수 있어요. <br />
            먼저 스페이스를 선택하고, 가능하면 Folder/File까지 좁혀 보세요.
          </div>
        </div>
      </div>
      <Image src={JiraGuide} alt="Guide" className="w-full" />
    </div>
  );
}

export function GithubGuideCard({ onClose }: GuideCardProps) {
  return (
    <div className="border-neutral-3 shadow-card flex w-190 flex-col items-start gap-8 rounded-3xl border bg-white p-5">
      <div className="flex flex-col items-start gap-5 self-stretch">
        <div className="flex items-center justify-between self-stretch">
          <div className="bg-gray-70 flex items-center justify-center gap-2 rounded-[10px] px-2 py-1 text-white">
            <IconHelp className="h-6 w-6 text-white" />
            <div className="text-heading-small">Github 스페이스 선택 가이드</div>
          </div>
          <button onClick={onClose} className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
            <IconX />
          </button>
        </div>
        <div className="flex flex-col items-start gap-1.5 self-stretch">
          <div className="text-heading-medium text-gray-90">
            캐치스턴트 AI에게 <span className="text-blue-55">참고할 범위</span>를 알려주세요
          </div>
          <div className="text-body-small text-gray-70 self-stretch">
            관련된 레포와 폴더를 지정하면 더 빠르고 정확한 답변을 받을 수 있어요.
            <br />
            먼저 Repository를 선택하고, 가능하면 Folder/File까지 좁혀 보세요.
          </div>
        </div>
      </div>
      <Image src={GitGuide} alt="Guide" className="w-full" />
    </div>
  );
}
