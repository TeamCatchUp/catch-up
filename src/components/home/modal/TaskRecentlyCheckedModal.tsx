import { useRef } from 'react';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import EditSquare from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import Link from '/public/icons/icon/link.svg';
import SlackLogo from '/public/icons/logo/Slack.svg';
import GithubLogo from '/public/icons/logo/GitHub.svg';
import ConfluenceLogo from '/public/icons/logo/Confluence.svg';
import WikiLogo from '/public/icons/icon/Wiki.svg';
import NotionLogo from '/public/icons/icon/Notion.svg';
import Add from '/public/icons/icon/add_small.svg';
import Chat from '/public/icons/icon/chat.svg';
import TaskManagerPart from '@/components/home/cardComponents/TaskManagePart';
import ToolTip from '@/components/common/ToolTip';

interface TaskRecentlyCheckedModalProps {
  task: TaskRecentlyCheckedCard;
  onClose: () => void;
}

const TaskRecentlyCheckedModal = ({ task, onClose }: TaskRecentlyCheckedModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div ref={modalRef} className="border-neutral-4 shadow-modal flex h-168 w-153.75 rounded-3xl border bg-white">
      <div className="flex w-153.75 flex-col gap-4 px-4 pt-5">
        {/* 헤더 */}
        <div className="flex flex-col gap-3 px-1.5">
          <div className="flex w-142.25 items-center justify-between gap-1.5">
            <span className="text-heading-large text-gray-80 max-w-109.75 truncate">{task.title}</span>
            <div className="flex gap-2">
              <button className="icon-button-only-gray group relative flex h-7.5 w-7.5 cursor-pointer items-center justify-center">
                <EditSquare className="h-6 w-6 text-gray-50" />
                <ToolTip text="인수인계 시작하기" />
              </button>
              <button className="icon-button-only-gray group relative flex h-7.5 w-7.5 cursor-pointer items-center justify-center">
                <Share className="h-6 w-6 text-gray-50" />
                <ToolTip text="자료 공유하기" />
              </button>
              <button className="icon-button-only-gray flex h-7.5 w-7.5 cursor-pointer items-center justify-center">
                <Cancel onClick={onClose} className="h-6 w-6 text-gray-50" />
              </button>
            </div>
          </div>
          <TaskManagerPart depart={task.depart} manager={task.manager} />
        </div>

        <div className="bg-neutral-4 flex h-px w-145.75"></div>

        {/* 관련 Wiki */}
        <div className="flex flex-col gap-1.5">
          <div className="flex h-7 justify-between">
            <span className="text-body-xsmall flex items-end px-1.5 text-gray-50">관련 Wiki</span>
            <button className="text-button-primary-blue flex cursor-pointer items-center gap-0.5 px-1.5 py-1">
              <span className="text-body-xsmall text-blue-55 relative top-px left-px">자세히 보기</span>
              <ArrowRight className="h-4.5 w-4.5 text-blue-50" />
            </button>
          </div>

          <div className="flex flex-col gap-1.5">
            {/* 24->30 */}
            <div className="scroll-x-hover max-h-30 overflow-x-scroll">
              <div className="flex gap-3">
                <div className="border-neutral-3 flex w-82.75 shrink-0 cursor-pointer flex-col gap-1.5 rounded-xl border p-3">
                  <div className="flex justify-between">
                    <span className="text-body-small text-gray-80 max-w-58 truncate">
                      한도 계산 API 리팩토링 현황 공유 및 머시기
                    </span>
                    <span className="text-body-xsmall text-green-60 bg-green-10 rounded-md2 flex items-center justify-center px-1.5 py-0.5 text-center whitespace-nowrap">
                      부서O
                    </span>
                  </div>
                  <span className="text-body-xsmall line-clamp-2 text-gray-50">
                    외부 PG 연동 과정에서 발생하는 응답 지연 장애 및 장애 상황에 대해 탐지, 알림, 대응 절차를 정리한
                    가이드 문서
                  </span>
                </div>
                <div className="border-neutral-3 flex w-82.75 shrink-0 cursor-pointer flex-col gap-1.5 rounded-xl border p-3">
                  <div className="flex justify-between">
                    <span className="text-body-small text-gray-80 max-w-58 truncate">
                      한도 계산 API 리팩토링 현황 공유 및 머시기
                    </span>
                    <span className="text-body-xsmall text-green-60 bg-green-10 rounded-md2 flex items-center justify-center px-1.5 py-0.5 text-center whitespace-nowrap">
                      부서O
                    </span>
                  </div>
                  <span className="text-body-xsmall line-clamp-2 text-gray-50">
                    현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 운영 반영 시
                    유의사항 머시기머시기ㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁ
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 관련 파일 */}
          <div className="relative flex max-w-145.75 flex-col gap-2.5">
            <div className="text-body-xsmall px-1.5 text-gray-50">관련 파일</div>
            <div className="flex flex-wrap gap-2.5">
              <div className="capsule-button-outline-mono flex cursor-pointer items-center gap-1.5 px-3 py-1.5">
                <Link className="h-5 w-5" />
                <span className="text-body-small text-gray-80">pg-latency_monitoring_conig.yaml</span>
              </div>
              <div className="capsule-button-outline-mono flex cursor-pointer items-center gap-1.5 px-3 py-1.5">
                <Link className="h-5 w-5" />
                <span className="text-body-small text-gray-80">일본 시장 진출 가설 및 검증 결과</span>
              </div>
              <div className="capsule-button-outline-mono flex cursor-pointer items-center gap-1.5 px-3 py-1.5">
                <SlackLogo className="h-5 w-5" />
                <span className="text-body-small text-gray-80">일본 시장 조사하면서 나온 포인트들</span>
              </div>
            </div>
          </div>
        </div>

        {/* 관련 지라 티켓 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-body-xsmall px-1.5 text-gray-50">관련 지라 티켓</span>
          <div className="flex gap-2.5">
            <span className="bg-violet-5 text-body-small text-grat-70 flex rounded-full px-4 py-1.5">
              일본 시장 진출 리서치 범위 및 방향 정의
            </span>
            <span className="bg-light-blue-5 text-body-small text-grat-70 flex rounded-full px-4 py-1.5">
              일본 진출 가설 검증 결과 정리
            </span>
          </div>
        </div>

        {/* 관련 업무 질문 히스토리 */}
        <div className="flex flex-col gap-1.5">
          <div className="text-body-xsmall px-1.5 text-gray-50">관련 업무 질문 히스토리</div>
          <button className="text-button-primary-blue flex h-7 w-23 cursor-pointer items-center justify-center gap-0.5 px-1.5 py-1">
            <Add className="h-4.5 w-4.5 text-blue-50" />
            <span className="text-blue-55 text-body-xsmall relative top-px whitespace-nowrap">새 질문하기</span>
          </button>
          <div className="flex flex-col gap-1">
            <div className="icon-button-only-gray flex cursor-pointer items-center gap-2 rounded-xl px-2 py-1">
              <div className="border-neutral-3 bg-neutral-1 flex items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="body-small text-gray-80 max-w-111.25 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30 relative top-px flex items-center">2025.12.14</span>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="icon-button-only-gray flex cursor-pointer items-center gap-2 rounded-xl px-2 py-1">
              <div className="border-neutral-3 bg-neutral-1 flex items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="body-small text-gray-80 max-w-111.25 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30 relative top-px flex items-center">2025.12.14</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskRecentlyCheckedModal;
