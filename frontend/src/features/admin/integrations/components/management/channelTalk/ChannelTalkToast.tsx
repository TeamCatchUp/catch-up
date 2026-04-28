'use client';

interface ChannelTalkToastProps {
  /** 1행 제목 (semibold) — 디자인은 `whitespace-nowrap`이라 가로 max-w 안에서만 줄바꿈 */
  title: string;
  /** 2행 본문 설명 (regular) — 선택 */
  description?: string;
}

/**
 * 채널톡 검증 결과 토스트 — 성공/실패 모두 동일 시각, 텍스트만 다름.
 *
 * 컨테이너는 fixed width 없이 컨텐츠 폭에 따라 가변. 토스트 컨테이너에서 z-toast로 띄워 사용.
 *
 * @example
 * <ChannelTalkToast title="연결에 성공했어요." description="이제 동기화를 시작할 수 있어요." />
 */
export default function ChannelTalkToast({ title, description }: ChannelTalkToastProps) {
  return (
    <div className="bg-material-alert-modal flex items-center justify-center gap-3 overflow-clip rounded-xl p-4 shadow-[0_6px_25px_0_rgba(0,0,0,0.28)]">
      <div className="flex max-w-67 flex-col items-center justify-center gap-3">
        <p className="text-heading-small text-content-inverse text-center whitespace-nowrap">{title}</p>
        {description ? (
          <p className="text-label-small text-content-inverse w-full text-center">{description}</p>
        ) : null}
      </div>
    </div>
  );
}
