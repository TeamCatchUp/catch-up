import Cancel from '@/public/icons/icon/cancel.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

interface EmbeddingRetryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetName: string;
  /** 전체 레코드 수 */
  totalCount: number;
  /** 성공 레코드 수 */
  successCount: number;
  /** 실패 레코드 수 */
  failedCount: number;
  /** 재시도 횟수 (0이면 첫 재시도, 1+이면 재시도 후 재시도) */
  retryAttempt: number;
  /** 재시도 진행 중 레코드 수 (retryAttempt > 0일 때 표시) */
  retryingCount?: number;
  onConfirm: () => void;
}

const EmbeddingRetryModal = ({
  open,
  onOpenChange,
  targetName: _targetName,
  totalCount,
  successCount,
  failedCount,
  retryAttempt,
  retryingCount = 0,
  onConfirm,
}: EmbeddingRetryModalProps) => {
  const isFirstRetry = retryAttempt === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-normal bg-fill-normal flex w-140 flex-col gap-4 rounded-3xl border p-0 py-5 shadow-modal"
      >
        {/* Header: h-9, px-6, gap-3 */}
        <div className="flex h-9 items-center gap-3 px-6">
          <DialogTitle className="text-heading-large text-content-normal flex-1">임베딩 재시도</DialogTitle>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="flex size-9 cursor-pointer items-center justify-center rounded-lg p-1.5"
          >
            <Cancel className="text-content-normal size-6" />
          </button>
        </div>

        {/* Body: border-t, pt-6, px-6, gap-6 */}
        <div className="border-edge-assistive flex flex-col gap-6 overflow-x-clip overflow-y-auto border-t px-6 pt-6">
          {/* 임베딩 현황: gap-2.5 */}
          <div className="flex flex-col gap-2.5">
            {/* 현황 헤더: gap-5 */}
            <div className="flex items-center gap-5">
              <h3 className="text-heading-medium text-content-normal flex-1">임베딩 현황</h3>
              <span className="text-label-small text-content-alternative max-w-100">
                전체 {totalCount.toLocaleString()}개
              </span>
            </div>

            {/* 재시도 후: 재시도 카드 (full-width) */}
            {!isFirstRetry && (
              <div className="bg-fill-strong flex items-center gap-3 rounded-xl p-3">
                <div className="bg-fill-normal flex shrink-0 items-center justify-center rounded-xl p-2">
                  <IconRotate className="text-content-normal size-7" />
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-body-small text-content-normal">임베딩 재시도</span>
                  <span className="text-body-small text-content-alternative">{retryingCount.toLocaleString()}개</span>
                </div>
              </div>
            )}

            {/* 성공 / 실패 카드: gap-3 */}
            <div className="flex gap-3">
              <div className="bg-fill-strong flex flex-1 items-center gap-3 rounded-xl p-3">
                <div className="bg-fill-normal flex shrink-0 items-center justify-center rounded-xl p-2">
                  <IconCheckCircleFilled className="text-status-positive size-7" />
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-body-small text-status-positive">임베딩 성공</span>
                  <span className="text-body-small text-content-alternative">{successCount.toLocaleString()}개</span>
                </div>
              </div>
              <div className="bg-fill-strong flex flex-1 items-center gap-3 rounded-xl p-3">
                <div className="bg-fill-normal flex shrink-0 items-center justify-center rounded-xl p-2">
                  <IconErrorFilled className="text-status-destructive size-7" />
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-body-small text-status-destructive">임베딩 실패</span>
                  <span className="text-body-small text-content-alternative">{failedCount.toLocaleString()}개</span>
                </div>
              </div>
            </div>
          </div>

          {/* 임베딩 제안: gap-2 */}
          <div className="flex flex-col gap-2">
            <span className="text-label-small text-content-neutral">임베딩 제안</span>
            {isFirstRetry ? (
              <>
                <h3 className="text-heading-medium text-content-normal">
                  실패한 {failedCount.toLocaleString()}개만 다시 해볼까요?
                </h3>
                <p className="text-body-small text-content-neutral">
                  완료되지 못한 것들만 다시 처리해요. 훨씬 빠르게 끝날 거예요.
                </p>
              </>
            ) : (
              <>
                <h3 className="text-heading-medium text-content-normal">
                  {failedCount.toLocaleString()}개가 완료되지 못했어요
                </h3>
                <p className="text-body-small text-content-neutral">
                  일시적인 문제일 수 있어요. 한 번 더 시도해볼까요?
                  <br />
                  만약, 모든 재시도가 실패한 경우, Catch Up에 문의해주세요.
                </p>
              </>
            )}
          </div>
        </div>

        {/* Footer: h-9, px-6, gap-3, justify-end */}
        <div className="flex h-9 items-start justify-end gap-3 px-6">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="border-edge-normal bg-fill-normal text-body-small text-content-normal flex h-9 cursor-pointer items-center justify-center overflow-clip rounded-full border px-3 py-1.5"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="bg-fill-primary text-body-small flex h-9 cursor-pointer items-center justify-center overflow-clip rounded-full px-3 py-1.5 text-white"
          >
            다시 임베딩하기
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmbeddingRetryModal;
