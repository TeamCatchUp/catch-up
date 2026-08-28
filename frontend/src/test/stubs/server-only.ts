// Next.js는 'server-only'를 번들 레이어에 따라 내부 alias로 처리하므로 패키지 설치 없이 동작한다.
// Vitest에는 그 처리가 없어 같은 역할의 빈 모듈로 alias한다(vitest.config.ts).
export {};
