'use client';

import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import IconAdd from '@/public/icons/icon/add.svg';
import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconError from '@/public/icons/icon/error.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconLink from '@/public/icons/icon/link.svg';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import type { MappingUploadResponse, VendorType } from '../../../types/api';

// ─── 벤더 설정 ───

interface VendorConfig {
  vendor: VendorType;
  label: string;
  helperText: string;
}

const VENDOR_CONFIGS: VendorConfig[] = [
  {
    vendor: 'atlassian',
    label: 'Atlassian CSV 업로드',
    helperText: 'Atlassian에서 내보낸 이용자 CSV 파일을 업로드해주세요.',
  },
  {
    vendor: 'github',
    label: 'Github CSV 업로드',
    helperText: '사전에 공유된 GitHub 템플릿 형식의 CSV 파일을 업로드해주세요.',
  },
  {
    vendor: 'slack',
    label: 'Slack CSV 업로드',
    helperText: 'Slack에서 내보낸 이용자 CSV 파일을 업로드해주세요.',
  },
];

const ACCEPTED_EXTENSIONS = '.csv,.xlsx,.xls';

const isValidFileExtension = (fileName: string): boolean => {
  const ext = fileName.split('.').pop()?.toLowerCase();
  return ext === 'csv' || ext === 'xlsx' || ext === 'xls';
};

// ─── VendorFileUploader ───

interface VendorFileUploaderProps {
  label: string;
  helperText: string;
  file: File | null;
  error: string | null;
  onFileSelect: (file: File) => void;
  onFileRemove: () => void;
}

/** 벤더별 CSV 파일 업로더 (빈 상태 / 업로드됨 / 에러) */
const VendorFileUploader = ({
  label,
  helperText,
  file,
  error,
  onFileSelect,
  onFileRemove,
}: VendorFileUploaderProps) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onFileSelect(f);
    e.target.value = '';
  };

  return (
    <div className="flex flex-col gap-1">
      {/* 라벨 + 필수 표시 — Figma: gap-4(4px), 필수 dot 5px */}
      <div className="flex items-center gap-1">
        <span className="text-body-small text-gray-80 font-medium">{label}</span>
        <span className="bg-red-40 size-[5px] rounded-full" />
      </div>

      <input ref={inputRef} type="file" accept={ACCEPTED_EXTENSIONS} hidden onChange={handleChange} />

      {file ? (
        /* 파일 선택됨: 링크 아이콘 + 파일명 + X */
        <div className="border-neutral-3 flex items-center gap-2 rounded-lg border px-3 py-2">
          <IconLink className="size-4 shrink-0 text-gray-50" />
          <span className="text-body-xsmall text-gray-70 flex-1 truncate">{file.name}</span>
          <button onClick={onFileRemove} className="text-gray-40 hover:text-gray-60 shrink-0 cursor-pointer">
            <IconCancelSmall className="size-5" />
          </button>
        </div>
      ) : (
        /* 파일 미선택: 업로더 박스 + 헬퍼/에러 */
        <>
          <button
            onClick={() => inputRef.current?.click()}
            className="border-neutral-3 bg-neutral-1 hover:bg-neutral-2 flex size-30 cursor-pointer items-center justify-center rounded-xl border transition-colors"
          >
            <IconAdd className="text-gray-40 size-6" />
          </button>

          {error ? (
            <div className="flex items-center gap-0.5">
              <IconError className="text-red-40 size-4 shrink-0" />
              <span className="text-label-xsmall text-red-40">{error}</span>
            </div>
          ) : (
            <p className="text-label-xsmall text-gray-50">{helperText}</p>
          )}
        </>
      )}
    </div>
  );
};

// ─── CsvUploadModal ───

interface CsvUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CsvUploadModal = ({ open, onOpenChange }: CsvUploadModalProps) => {
  const [files, setFiles] = useState<Record<VendorType, File | null>>({
    atlassian: null,
    github: null,
    slack: null,
  });
  const [errors, setErrors] = useState<Record<VendorType, string | null>>({
    atlassian: null,
    github: null,
    slack: null,
  });

  const queryClient = useQueryClient();

  const hasAnyFile = Object.values(files).some((f) => f !== null);

  const resetState = () => {
    setFiles({ atlassian: null, github: null, slack: null });
    setErrors({ atlassian: null, github: null, slack: null });
  };

  const handleFileSelect = (vendor: VendorType, file: File) => {
    if (!isValidFileExtension(file.name)) {
      setErrors((prev) => ({
        ...prev,
        [vendor]: '파일 형식이 올바르지 않습니다. 알맞은 파일을 사용해주세요.',
      }));
      return;
    }
    setFiles((prev) => ({ ...prev, [vendor]: file }));
    setErrors((prev) => ({ ...prev, [vendor]: null }));
  };

  const handleFileRemove = (vendor: VendorType) => {
    setFiles((prev) => ({ ...prev, [vendor]: null }));
    setErrors((prev) => ({ ...prev, [vendor]: null }));
  };

  const uploadMutation = useMutation({
    mutationKey: ['mapping', 'vendorUpload'] as const,
    mutationFn: async () => {
      const uploads = VENDOR_CONFIGS.filter(({ vendor }) => files[vendor]).map(async ({ vendor }) => {
        const formData = new FormData();
        formData.append('file', files[vendor]!);
        const res = await api.post<MappingUploadResponse>(API.mapping.vendorUpload(vendor), formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        return { vendor, data: res.data };
      });

      return Promise.all(uploads);
    },
    onSuccess: () => {
      toast('업로드가 완료되었습니다.', {
        description: '데이터가 정상적으로 반영되었습니다.',
      });
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'syncStatus'] });
      resetState();
      onOpenChange(false);
    },
    onError: () => {
      toast('일시적인 오류가 발생했습니다.', {
        description: '잠시 후 다시 시도해주세요.',
      });
    },
  });

  const handleSubmit = () => {
    if (!hasAnyFile || uploadMutation.isPending) return;
    uploadMutation.mutate();
  };

  const handleClose = (nextOpen: boolean) => {
    if (uploadMutation.isPending) return;
    if (!nextOpen) resetState();
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent hideClose className="max-w-110 gap-0 rounded-2xl p-0">
        {/* Figma 모달: pt-3(12px) pb-4(16px) px-5(20px), gap-2(8px) scroll-wrapper↔footer */}
        <div className="flex flex-col gap-2 px-5 pt-3 pb-4">
          {/* ── Scroll wrapper (header + content) ── */}
          <div className="flex max-h-94.5 flex-col gap-1.5 overflow-clip">
            {/* 헤더: h-9(36px), 제목 + 닫기 */}
            <div className="flex h-9 shrink-0 items-center justify-between">
              <DialogTitle className="text-heading-medium text-gray-80">CSV 파일 업로드하기</DialogTitle>
              <button
                onClick={() => handleClose(false)}
                className="hover:text-gray-70 flex size-7 cursor-pointer items-center justify-center rounded-full text-gray-50"
              >
                <IconCancelSmall className="size-6" />
              </button>
            </div>

            {/* 콘텐츠: border-t, pt-4(16px), gap-3(12px) guide↔vendors */}
            <div className="border-neutral-3 flex flex-col gap-3 overflow-y-auto border-t pt-4">
              {/* CSV 가이드 버튼 — Figma: h-30(30px), gap-1(4px), px-2(8px), py-1(4px), icon 24px */}
              <button className="border-neutral-3 text-body-xsmall text-gray-80 hover:bg-neutral-1 flex h-7.5 w-fit cursor-pointer items-center gap-1 rounded-lg border bg-white px-2 py-1">
                <IconFile className="text-gray-70 size-5 shrink-0" />
                CSV 업로드 가이드(PDF) 보기
              </button>

              {/* 벤더 섹션 — gap-6(24px) between sections */}
              <div className="flex flex-col gap-6">
                {VENDOR_CONFIGS.map(({ vendor, label, helperText }) => (
                  <VendorFileUploader
                    key={vendor}
                    label={label}
                    helperText={helperText}
                    file={files[vendor]}
                    error={errors[vendor]}
                    onFileSelect={(file) => handleFileSelect(vendor, file)}
                    onFileRemove={() => handleFileRemove(vendor)}
                  />
                ))}
              </div>

              <div className="h-2 shrink-0" />
            </div>
          </div>

          {/* ── 푸터: gap-2.5(10px) ── */}
          <div className="flex items-center justify-end gap-2.5">
            <Button
              variant="capsule-outline-mono"
              size="md"
              onClick={() => handleClose(false)}
              disabled={uploadMutation.isPending}
            >
              취소
            </Button>
            <Button
              variant="capsule-solid-primary"
              size="md"
              disabled={!hasAnyFile || uploadMutation.isPending}
              onClick={handleSubmit}
            >
              {uploadMutation.isPending ? '업로드 중...' : '등록'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CsvUploadModal;
