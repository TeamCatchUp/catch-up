import { useEffect } from 'react';

// ESC 키 입력 시 닫기 로직(onClose)을 실행하는 공통 훅
export function useEscapeKey(onClose: () => void) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    // 전역 keydown 이벤트를 등록하고, 언마운트 시 정리한다.
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
    };
  }, [onClose]);
}
