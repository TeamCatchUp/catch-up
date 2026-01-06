import { useRef } from 'react';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import LoadingProfile from '/public/icons/icon/loading_profile.svg';

const members = [
  { name: '팀원G', role: 'PM' },
  { name: '팀원G', role: 'Designer' },
  { name: '팀원G', role: 'Developer' },
  { name: '팀원G', role: 'Tester' },
  { name: '팀원G', role: 'Backend' },
  { name: '팀원G', role: 'Frontend' },
  { name: '팀원G', role: 'QA' },
  { name: '팀원G', role: 'PM' },
];

const ShareButtonModal = ({ onClose }: { onClose: () => void }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useOutsideClick(modalRef, onClose);
  useEscapeKey(onClose);

  return (
    <div
      ref={modalRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-modal-title"
      className="border-neutral-4 shadow-dropdown-menu flex h-123 w-95 flex-col gap-3 rounded-2xl border bg-white px-1.5 pt-3"
    >
      <header className="flex items-center justify-between gap-1.5 px-1">
        <label htmlFor="share-input" className="sr-only">
          이메일 또는 그룹 입력
        </label>
        <input
          id="share-input"
          className="text-body-small placeholder-gray-30 focus:caret-blue-30 focus:bg-neutral-1 focus:border-blue-30 border-neutral-3 h-11.5 w-72.25 rounded-xl border p-3 transition-colors outline-none"
          placeholder="이메일 또는 그룹을 입력하세요."
        />
        <button className="text-body-medium h-10 cursor-pointer rounded-lg border bg-blue-50 px-4 py-1.5 whitespace-nowrap text-white">
          초대
        </button>
      </header>

      <section aria-labelledby="share-modal-title" className="overflow-y-auto">
        <h2 id="share-modal-title" className="sr-only">
          초대 가능한 멤버 목록
        </h2>
        <ul className="flex flex-col gap-1.5">
          {members.map((member, index) => (
            <li
              key={index}
              className="hover:bg-neutral-2 focus:bg-neutral-2 flex h-12.75 w-91.25 cursor-pointer items-center gap-4 rounded-lg p-1 focus:outline-none"
              tabIndex={0}
            >
              <LoadingProfile className="h-10 w-10" />
              <div>
                <p className="text-body-small">{member.name}</p>
                <p className="text-body-xsmall text-gray-50">{member.role}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};

export default ShareButtonModal;
