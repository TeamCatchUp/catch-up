import { toast } from '@/shared/components/ui/toast';

/**
 * 지금 보고 있는 화면 주소를 클립보드에 담는다. 공유 링크 규격이 따로 없어 주소를 그대로 쓴다.
 * 실패해도 던지지 않는다 — 알림은 토스트 하나뿐이다.
 */
export async function copyCurrentPageLink() {
  try {
    await navigator.clipboard.writeText(window.location.href);
    toast('링크가 복사되었습니다.');
  } catch {
    toast('복사에 실패했습니다.');
  }
}
