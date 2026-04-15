'use client';

import { useState } from 'react';

import IconAddCircleFilled from '@/public/icons/icon/add_circle_filled.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import { Button } from '@/shared/components/ui/button';
import { Chip } from '@/shared/components/ui/chips';
import { Separator } from '@/shared/components/ui/separator';
import { cn } from '@/shared/utils/cn';

import { JOB_ROLE_OPTIONS, MAX_JOB_DESCRIPTION_LENGTH, MAX_JOB_TEXT_LENGTH } from '../../constants/preferencesConfig';
import type { JobRole } from '../../types/preferencesModel';
import StepHeader from '../StepHeader';

interface JobSelectionStepProps {
  selectedJob: JobRole | null;
  customJobText: string;
  jobDescription: string;
  onSaveJob: (job: JobRole | null, customJobText: string, jobDescription: string) => void;
}

export default function JobSelectionStep({
  selectedJob,
  customJobText,
  jobDescription,
  onSaveJob,
}: JobSelectionStepProps) {
  // Step 1 전체를 로컬 state로 관리, 저장 버튼 클릭 시에만 서버 전송
  const [localJob, setLocalJob] = useState<JobRole | null>(selectedJob);
  const [localJobText, setLocalJobText] = useState(customJobText);
  const [localDesc, setLocalDesc] = useState(jobDescription);
  const [jobFieldFocused, setJobFieldFocused] = useState(false);
  const [descFieldFocused, setDescFieldFocused] = useState(false);

  // 서버에 텍스트가 이미 저장되어 있는지 여부
  const hasSaved = selectedJob !== null;

  // 편집 모드 (저장된 상태에서 "수정" 버튼 클릭 시 진입)
  const [isEditing, setIsEditing] = useState(false);

  // 서버 데이터가 변경되면 로컬 state 동기화 (저장 후 응답 반영)
  const [prevServerData, setPrevServerData] = useState({ selectedJob, customJobText, jobDescription });
  if (
    selectedJob !== prevServerData.selectedJob ||
    customJobText !== prevServerData.customJobText ||
    jobDescription !== prevServerData.jobDescription
  ) {
    setPrevServerData({ selectedJob, customJobText, jobDescription });
    setLocalJob(selectedJob);
    setLocalJobText(customJobText);
    setLocalDesc(jobDescription);
    setIsEditing(false);
  }

  const isCustom = localJob === 'custom';
  const hasJob = localJob !== null;
  const isJobTextAtLimit = localJobText.length >= MAX_JOB_TEXT_LENGTH;
  const isDescAtLimit = localDesc.length >= MAX_JOB_DESCRIPTION_LENGTH;
  const isDescDisabled = isCustom && localJobText.trim().length === 0;

  // 읽기 전용 모드: 서버에 저장된 데이터가 있고, 로컬 칩이 서버와 같고, 편집 중이 아닐 때
  const isReadOnly = hasSaved && localJob === selectedJob && !isEditing;

  const handleChipClick = (chipValue: JobRole) => {
    const isSelected = localJob === chipValue;

    if (isSelected) {
      // 칩 해제: 로컬만 변경 (서버 전송은 저장 버튼에서)
      setLocalJob(null);
      setLocalJobText('');
      setLocalDesc('');
      setIsEditing(false);
    } else if (chipValue === selectedJob) {
      // 서버에 저장된 칩으로 돌아옴: 저장된 값 복원
      setLocalJob(chipValue);
      setLocalJobText(customJobText);
      setLocalDesc(jobDescription);
      setIsEditing(false);
    } else {
      // 새로운 칩 전환: 텍스트 비우기
      setLocalJob(chipValue);
      setLocalJobText('');
      setLocalDesc('');
      setIsEditing(true);
    }
  };

  const handleSave = () => {
    onSaveJob(localJob, localJobText, localDesc);
    setIsEditing(false);
  };

  const handleEdit = () => {
    setLocalJobText(customJobText);
    setLocalDesc(jobDescription);
    setIsEditing(true);
  };

  // 저장 버튼 활성화 조건
  const canSave = isCustom ? localJobText.trim().length > 0 : localJob !== null;

  return (
    <div className="border-edge-neutral flex flex-col gap-5 border-b py-5">
      <StepHeader stepNumber={1} title="직무 선택" description="어떤 일을 하고 계신가요? 그에 맞게 답해드릴게요." />

      {/* 칩 그리드 */}
      <div className="flex flex-wrap gap-2.5">
        {JOB_ROLE_OPTIONS.map((opt) => {
          const isSelected = localJob === opt.value;
          return (
            <Chip
              key={opt.value}
              variant="square"
              selected={isSelected}
              trailingIcon={isSelected ? <IconCheckCircleFilled /> : undefined}
              onClick={() => handleChipClick(opt.value)}
            >
              {opt.label}
            </Chip>
          );
        })}
      </div>

      {/* 직무 선택 후 표시되는 카드 */}
      {hasJob && (
        <div className="border-edge-assistive bg-fill-strong flex flex-col gap-5 overflow-clip rounded-xl border p-5">
          {/* "직접 입력" 선택 시: 직무 입력 필드 */}
          {isCustom && (
            <>
              <div className="flex flex-col gap-2.5">
                <div className="flex items-center gap-2.5">
                  <IconAddCircleFilled className="text-icon-primary size-6 shrink-0" />
                  <span className="text-heading-small text-content-normal">직무 직접 입력하기</span>
                </div>
                <div
                  className={cn(
                    'bg-fill-normal flex h-11.5 items-center rounded-lg p-3',
                    isReadOnly
                      ? 'border-edge-neutral border'
                      : isJobTextAtLimit
                        ? 'border-status-destructive border'
                        : jobFieldFocused
                          ? 'border-edge-primary border-[1.2px]'
                          : 'border-edge-neutral border',
                  )}
                >
                  <input
                    className={cn(
                      'text-body-small flex-1 bg-transparent outline-none',
                      isReadOnly
                        ? 'text-content-normal cursor-default'
                        : 'text-content-normal placeholder:text-content-assistive',
                    )}
                    placeholder="직무를 입력해주세요."
                    maxLength={MAX_JOB_TEXT_LENGTH}
                    value={localJobText}
                    onChange={(e) => setLocalJobText(e.target.value)}
                    onFocus={() => setJobFieldFocused(true)}
                    onBlur={() => setJobFieldFocused(false)}
                    readOnly={isReadOnly}
                  />
                  {!isReadOnly && (
                    <span className="text-body-small text-content-alternative shrink-0">
                      {localJobText.length}/{MAX_JOB_TEXT_LENGTH}
                    </span>
                  )}
                </div>
                {!isReadOnly && isJobTextAtLimit && (
                  <div className="flex items-center gap-0.5">
                    <IconErrorFilled className="text-status-destructive size-4 shrink-0" />
                    <span className="text-label-xsmall text-status-destructive">
                      {MAX_JOB_TEXT_LENGTH}자 내외로 입력해주세요.
                    </span>
                  </div>
                )}
              </div>
              {/* 구분선 */}
              <Separator />
            </>
          )}

          {/* 업무 설명 필드 */}
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2.5">
              <IconAddCircleFilled className="text-icon-primary size-6 shrink-0" />
              <span className="text-heading-small text-content-normal flex-1">주로 어떤 업무를 맡고 있나요?</span>
              {isReadOnly ? (
                <Button type="button" variant="box-soft-primary" size="md" onClick={handleEdit}>
                  수정
                </Button>
              ) : (
                <Button type="button" variant="box-solid-primary" size="md" disabled={!canSave} onClick={handleSave}>
                  저장
                </Button>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <div
                className={cn(
                  'flex h-11.5 items-center rounded-lg p-3',
                  isReadOnly
                    ? 'bg-fill-normal border-edge-neutral border'
                    : isDescDisabled
                      ? 'bg-fill-interaction-disable border-edge-neutral border'
                      : isDescAtLimit
                        ? 'bg-fill-normal border-status-destructive border'
                        : descFieldFocused
                          ? 'bg-fill-normal border-edge-primary border-[1.2px]'
                          : 'bg-fill-normal border-edge-neutral border',
                )}
              >
                <input
                  className={cn(
                    'text-body-small flex-1 bg-transparent outline-none',
                    isReadOnly
                      ? 'text-content-normal cursor-default'
                      : isDescDisabled
                        ? 'text-content-assistive cursor-not-allowed'
                        : 'text-content-normal placeholder:text-content-assistive',
                  )}
                  placeholder={isDescDisabled ? '직무를 먼저 입력해주세요.' : '주요 업무를 간단히 입력해주세요.'}
                  maxLength={MAX_JOB_DESCRIPTION_LENGTH}
                  value={localDesc}
                  onChange={(e) => setLocalDesc(e.target.value)}
                  onFocus={() => setDescFieldFocused(true)}
                  onBlur={() => setDescFieldFocused(false)}
                  disabled={isDescDisabled}
                  readOnly={isReadOnly}
                />
                {!isReadOnly && !isDescDisabled && (
                  <span className="text-body-small text-content-alternative shrink-0">
                    {localDesc.length}/{MAX_JOB_DESCRIPTION_LENGTH}
                  </span>
                )}
              </div>
              {!isReadOnly && isDescAtLimit && (
                <div className="flex items-center gap-0.5">
                  <IconErrorFilled className="text-status-destructive size-4 shrink-0" />
                  <span className="text-label-xsmall text-status-destructive">
                    {MAX_JOB_DESCRIPTION_LENGTH}자 내외로 입력해주세요.
                  </span>
                </div>
              )}
              {!isReadOnly && (
                <div className="text-label-xsmall text-content-alternative flex flex-col">
                  <span>{` 예) iOS 앱 성능 최적화와 배포 파이프라인을 주로 담당해요`}</span>
                  <span>{` 예) B2B 영업 제안서 작성과 고객사 기술 미팅 대응이 많아요`}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
