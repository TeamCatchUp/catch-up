/**
 * 완료 화면 배경. Figma의 이름 붙은 스타일 `onboarding`(fill 3겹)이고 대응 시맨틱 토큰이 없다.
 * 토큰이 생기면 이 상수를 지우고 클래스로 옮긴다 — 다크 값도 시안에 없다.
 */
export const ONBOARDING_COMPLETE_BACKGROUND = {
  backgroundColor: '#FFFFFF',
  backgroundImage: [
    'linear-gradient(180deg, rgba(255, 255, 255, 0.5) 0%, rgba(255, 255, 255, 0) 50%, rgba(255, 255, 255, 0.05) 100%)',
    'radial-gradient(circle at 50% 85%, rgba(105, 165, 255, 0.2) 0%, rgba(201, 222, 254, 0.2) 100%)',
  ].join(', '),
} as const;
