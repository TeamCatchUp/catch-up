// 신규 기능 업데이트 공지 (CATDEV-47).
// 새 공지 게시 시 ID를 바꿔 dismiss를 초기화한다 (예: doc-search-mode-v2).

export const FEATURE_UPDATE_NOTICE_ID = 'doc-search-mode-v1';

export const FEATURE_UPDATE_NOTICE = {
  id: FEATURE_UPDATE_NOTICE_ID,
  tagLabel: '신규 기능',
  title: '신규 기능 업데이트',
  subtitle: '문서 탐색 모드가 추가됐어요',
  imageSrc: '/image/notice/doc-mode-notice.png',
  imageAlt: '문서 탐색 모드 미리보기',
  ctaLabel: '지금 써보기',
  ctaHref: '/?mode=docs',
} as const;
