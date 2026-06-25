// 신규 기능 업데이트 공지.
// 새 공지 게시 시 ID를 바꿔 dismiss를 초기화한다 (예: catch-up-mcp-v2).

export const FEATURE_UPDATE_NOTICE_ID = 'catch-up-mcp-v1';

export const FEATURE_UPDATE_NOTICE = {
  id: FEATURE_UPDATE_NOTICE_ID,
  tagLabel: '신규 기능',
  title: 'Claude에서 Catch Up 검색 시작하기',
  subtitle: '새로운 기능 : Catch Up MCP',
  imageSrc: '/image/help/light/catch-up-mcp.png',
  imageDarkSrc: '/image/help/dark/catch-up-mcp.png',
  imageAlt: 'Catch Up MCP 미리보기',
  ctaLabel: '지금 연결하기',
  ctaHref: '/mypage/help/tutorial/4',
} as const;
