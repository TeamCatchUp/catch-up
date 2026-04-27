/**
 * ⚠️ MOCK DATA — REMOVE WHEN CHANNEL_TALK API READY
 *
 * 이 파일은 채널톡 연동 UI 퍼블리싱을 위한 정적 mock 데이터다.
 * 실제 API 연동이 준비되면 다음 절차로 깔끔하게 제거할 수 있도록 격리되어 있다.
 *
 * TODO(channel-talk-api): API 도입 시 제거 절차
 *   1. 본 파일 (`channelTalkMock.ts`) 삭제
 *   2. `hooks/useChannelTalkViewModel.ts` 안의 mock import 제거
 *      `useState(CHANNEL_TALK_MOCK_STATE)` → `useQuery(channelTalkQueries.state())` 1줄 교체
 *   3. `queries/channelTalk.queries.ts` 신규 작성 (실제 API 호출)
 *   4. 컴포넌트 코드는 단 한 줄도 변경되지 않음 (props는 model 타입에만 의존)
 *
 * 본 파일은 hooks/useChannelTalkViewModel.ts 외 어떤 곳에서도 import 되어선 안 됨.
 */

import type { ChannelTalkChannel, ChannelTalkConnectionState } from '../types/channelTalkModel';

const channels: ChannelTalkChannel[] = [
  {
    id: 'ch_001',
    name: '고객 문의',
    accessKey: '',
    accessSecret: '',
    webhookToken: '',
    syncInterval: '5min',
    documentSpaces: [],
    connectionStatus: 'idle',
  },
  {
    id: 'ch_002',
    name: '기술 지원',
    accessKey: '8m4p7d1c9k3v6r2t',
    accessSecret: 'sk_live_q1w2e3r4t5y6u7i8',
    webhookToken: 'wh_token_002_cccc3333dddd4444',
    syncInterval: '15min',
    documentSpaces: [
      {
        id: 'ds_001',
        name: 'API 문서',
        accessKey: 'dk_001_a1b2c3d4',
        accessSecret: 'ds_001_z9y8x7w6',
        syncInterval: '1hour',
      },
      {
        id: 'ds_002',
        name: '내부 운영 가이드',
        accessKey: 'dk_002_e5f6g7h8',
        accessSecret: 'ds_002_v5u4t3s2',
        syncInterval: '1hour',
      },
      {
        id: 'ds_003',
        name: 'FAQ 모음',
        accessKey: 'dk_003_i9j0k1l2',
        accessSecret: 'ds_003_r1q0p9o8',
        syncInterval: '6hour',
      },
    ],
    connectionStatus: 'entered',
  },
  {
    id: 'ch_003',
    name: '비즈니스 문의',
    accessKey: '2q7n9w5e3r1t6y4u',
    accessSecret: 'sk_live_z9x8c7v6b5n4m3l2',
    webhookToken: 'wh_token_003_eeee5555ffff6666',
    syncInterval: '30min',
    documentSpaces: [
      {
        id: 'ds_004',
        name: '제품 정책',
        accessKey: 'dk_004_m3n4o5p6',
        accessSecret: 'ds_004_n7m6l5k4',
        syncInterval: '1hour',
      },
      {
        id: 'ds_005',
        name: '판매 가이드',
        accessKey: 'dk_005_q7r8s9t0',
        accessSecret: 'ds_005_j3i2h1g0',
        syncInterval: '6hour',
      },
      {
        id: 'ds_006',
        name: '계약 템플릿',
        accessKey: 'dk_006_u1v2w3x4',
        accessSecret: 'ds_006_f9e8d7c6',
        syncInterval: '24hour',
      },
      {
        id: 'ds_007',
        name: '경쟁사 분석',
        accessKey: 'dk_007_y5z6a7b8',
        accessSecret: 'ds_007_b5a4z3y2',
        syncInterval: '24hour',
      },
      {
        id: 'ds_008',
        name: '제안서 템플릿',
        accessKey: 'dk_008_c9d0e1f2',
        accessSecret: 'ds_008_x1w0v9u8',
        syncInterval: '6hour',
      },
    ],
    connectionStatus: 'tested',
  },
  {
    id: 'ch_004',
    name: '결제 문제',
    accessKey: '',
    accessSecret: '',
    webhookToken: '',
    syncInterval: '5min',
    documentSpaces: [
      {
        id: 'ds_009',
        name: '결제 정책',
        accessKey: 'dk_009_g3h4i5j6',
        accessSecret: 'ds_009_t7s6r5q4',
        syncInterval: '1hour',
      },
      {
        id: 'ds_010',
        name: '환불 가이드',
        accessKey: 'dk_010_k7l8m9n0',
        accessSecret: 'ds_010_p3o2n1m0',
        syncInterval: '1hour',
      },
      {
        id: 'ds_011',
        name: '결제 오류 케이스',
        accessKey: 'dk_011_o1p2q3r4',
        accessSecret: 'ds_011_l9k8j7i6',
        syncInterval: '6hour',
      },
      {
        id: 'ds_012',
        name: '청구서 양식',
        accessKey: 'dk_012_s5t6u7v8',
        accessSecret: 'ds_012_h5g4f3e2',
        syncInterval: '24hour',
      },
    ],
    connectionStatus: 'error',
    errorMessage: '필수 키가 입력되지 않았습니다. 모든 항목을 채워주세요.',
  },
  {
    id: 'ch_005',
    name: '기능 요청',
    accessKey: 'abcdefgabcdefgabcdefgabcdefgabcdefgabcdefgabcdefgabcdefg',
    accessSecret: 'sk_live_w7q6e5r4t3y2u1i0',
    webhookToken: 'wh_token_005_iiii9999jjjj0000',
    syncInterval: '1hour',
    documentSpaces: [
      {
        id: 'ds_013',
        name: '제품 로드맵',
        accessKey: 'dk_013_w9x0y1z2',
        accessSecret: 'ds_013_d1c0b9a8',
        syncInterval: '6hour',
      },
      {
        id: 'ds_014',
        name: '릴리즈 노트',
        accessKey: 'dk_014_a3b4c5d6',
        accessSecret: 'ds_014_z7y6x5w4',
        syncInterval: '6hour',
      },
      {
        id: 'ds_015',
        name: '기능 명세서',
        accessKey: 'dk_015_e7f8g9h0',
        accessSecret: 'ds_015_v3u2t1s0',
        syncInterval: '1hour',
      },
      {
        id: 'ds_016',
        name: '디자인 시스템',
        accessKey: 'dk_016_i1j2k3l4',
        accessSecret: 'ds_016_r9q8p7o6',
        syncInterval: '24hour',
      },
      {
        id: 'ds_017',
        name: 'UX 리서치',
        accessKey: 'dk_017_m5n6o7p8',
        accessSecret: 'ds_017_n5m4l3k2',
        syncInterval: '24hour',
      },
      {
        id: 'ds_018',
        name: '고객 인터뷰',
        accessKey: 'dk_018_q9r0s1t2',
        accessSecret: 'ds_018_j1i0h9g8',
        syncInterval: '24hour',
      },
    ],
    connectionStatus: 'editing',
  },
];

/**
 * 채널톡 mock 연동 상태.
 * - 헤드라인: "5개 채널 · 18개 도큐먼트 연결됨" (Figma node 12045:47583 매칭)
 * - 5개 채널이 각각 5가지 connectionStatus를 시연 (idle / entered / tested / error / editing)
 */
export const CHANNEL_TALK_MOCK_STATE: ChannelTalkConnectionState = {
  connected: true,
  lastSyncedAt: '2026. 2. 9. 01:31',
  channels,
};
