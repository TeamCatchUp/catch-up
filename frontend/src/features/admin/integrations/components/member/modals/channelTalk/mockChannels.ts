export interface ChannelTalkDocumentSpace {
  space_id: string;
  display_name: string;
}

export interface ChannelTalkChannel {
  channel_id: string;
  display_name: string;
  document_spaces: ChannelTalkDocumentSpace[];
}

export const MOCK_CHANNEL_TALK_CHANNELS: ChannelTalkChannel[] = [
  {
    channel_id: 'ch-001',
    display_name: '프로덕트 운영',
    document_spaces: [
      { space_id: 'sp-001', display_name: '프로덕트 운영 매뉴얼' },
      { space_id: 'sp-002', display_name: 'CS 응대 가이드라인' },
      { space_id: 'sp-003', display_name: '주간 운영 회고록' },
    ],
  },
  {
    channel_id: 'ch-002',
    display_name: '엔지니어링 일반',
    document_spaces: [
      { space_id: 'sp-004', display_name: '백엔드 온보딩 문서' },
      { space_id: 'sp-005', display_name: '프론트엔드 컨벤션' },
      { space_id: 'sp-006', display_name: '인프라 운영 플레이북' },
      { space_id: 'sp-007', display_name: '코드 리뷰 가이드' },
    ],
  },
  {
    channel_id: 'ch-003',
    display_name: '디자인 시스템',
    document_spaces: [
      { space_id: 'sp-008', display_name: '디자인 토큰 정의서' },
      { space_id: 'sp-009', display_name: '컴포넌트 사용 규칙' },
    ],
  },
  {
    channel_id: 'ch-004',
    display_name: '고객 지원',
    document_spaces: [
      { space_id: 'sp-010', display_name: 'FAQ 모음' },
      { space_id: 'sp-011', display_name: '환불 정책' },
      { space_id: 'sp-012', display_name: '고객 인터뷰 노트' },
    ],
  },
  {
    channel_id: 'ch-005',
    display_name: '마케팅',
    document_spaces: [
      { space_id: 'sp-013', display_name: '캠페인 기획서' },
      { space_id: 'sp-014', display_name: '브랜드 가이드' },
    ],
  },
  {
    channel_id: 'ch-006',
    display_name: '데이터 분석',
    document_spaces: [
      { space_id: 'sp-015', display_name: '대시보드 인덱스' },
      { space_id: 'sp-016', display_name: '데이터 정의서' },
      { space_id: 'sp-017', display_name: '실험 결과 아카이브' },
    ],
  },
  {
    channel_id: 'ch-007',
    display_name: '인사·총무',
    document_spaces: [
      { space_id: 'sp-018', display_name: '복리후생 안내' },
      { space_id: 'sp-019', display_name: '연차 사용 규정' },
    ],
  },
  {
    channel_id: 'ch-008',
    display_name: '재무',
    document_spaces: [
      { space_id: 'sp-020', display_name: '경비 처리 가이드' },
      { space_id: 'sp-021', display_name: '월별 결산 자료' },
    ],
  },
  {
    channel_id: 'ch-009',
    display_name: '리서치',
    document_spaces: [
      { space_id: 'sp-022', display_name: '사용자 리서치 리포트' },
      { space_id: 'sp-023', display_name: '경쟁사 분석' },
    ],
  },
  {
    channel_id: 'ch-010',
    display_name: '제품 출시 준비',
    document_spaces: [
      { space_id: 'sp-024', display_name: '런치 체크리스트' },
      { space_id: 'sp-025', display_name: '릴리즈 노트 초안' },
      { space_id: 'sp-026', display_name: '미디어 키트' },
    ],
  },
];
