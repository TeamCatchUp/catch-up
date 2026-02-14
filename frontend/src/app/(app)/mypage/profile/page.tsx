'use client';

import { useUserStore } from '@/shared/store/userStore';

import EditPencil from '/public/icons/icon/edit_pencil.svg';
import Profile from '/public/icons/icon/profile.svg';

/**
 * 마이페이지 프로필 화면을 렌더링
 */
const Page = () => {
  const { user } = useUserStore();

  return (
    <div className="flex flex-col">
      <div className="bg-neutral-1 h-60 w-full" />
      <div className="mx-auto -mt-15.5 flex w-268 flex-col items-center">
        <div className="mb-8 flex w-268 items-end justify-between px-16">
          <div className="flex items-end gap-4">
            <Profile className="h-31 w-31 rounded-[28px] border-[4px] border-white" />
            <div className="flex flex-col">
              <span className="text-heading-xlarge text-gray-80">{user?.name ?? ''}</span>
              <div className="flex gap-1 text-gray-50">
                <span className="text-body-small">사업개발팀</span>
                <span className="text-body-xsmall">|</span>
                <span className="text-body-small">PM</span>
              </div>
            </div>
          </div>
          <button className="box-button-outline-gray flex h-10 cursor-pointer items-center gap-1.5 px-4 py-1.5">
            <EditPencil className="h-6 w-6" />
            <span className="text-body-medium relative top-px text-gray-70">정보 수정하기</span>
          </button>
        </div>

        <div className="flex flex-col gap-8">
          <div className="flex w-268 flex-col gap-1 px-16">
            <div className="bg-neutral-1 rounded-md px-5 py-1.5">
              <span className="text-heading-small text-gray-70">소속 정보</span>
            </div>
            <div className="text-body-small flex flex-col px-5">
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">조직 / 직책</span>
                <span className="text-gray-50">사업개발팀</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">직무 / 직군</span>
                <span className="text-gray-50">PM</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">직위</span>
                <span className="text-gray-50">Tech</span>
              </div>
            </div>
          </div>

          <div className="flex w-268 flex-col gap-1 px-16">
            <div className="bg-neutral-1 rounded-md px-5 py-1.5">
              <span className="text-heading-small text-gray-70">기본 정보</span>
            </div>
            <div className="text-body-small flex flex-col px-5">
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">이름</span>
                <span className="text-gray-50">{user?.name ?? ''}</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">메일 / 번호</span>
                <span className="text-gray-50">{user?.email ?? ''}</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">주민등록번호</span>
                <span className="text-gray-50">020731-432343</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">연락처</span>
                <span className="text-gray-50">+82-10-2958-5214</span>
              </div>
              <div className="border-neutral-3 flex gap-6 border-b py-3">
                <span className="w-20 text-gray-70">주소</span>
                <span className="text-gray-50">서울시 마포구 합정로</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Page;
