import type { ReactNode } from 'react';

import StatusErrorPage from '@/shared/components/status/StatusErrorPage';
import { STATUS_IMAGES } from '@/shared/components/status/statusImages';
import { cn } from '@/shared/utils/cn';

import type { FigmaLabCase } from '../types';
import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';

function StatusPreview({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return <div className={cn('h-[625px] bg-background-normal-normal', dark && 'dark')}>{children}</div>;
}

export const forbiddenStatusLightFigmaCase: FigmaLabCase = {
  id: 'status-forbidden-light',
  groupId: 'shared-status',
  owner: 'shared',
  component: 'StatusErrorPage',
  state: 'light',
  kind: 'page',
  title: 'Status / 403 Light',
  description: '권한이 없는 상태 화면의 라이트 테마 레이아웃을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-183816&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '10328:183816',
  },
  targetRoute: '/agent-studio/[agentSpecId]/edit',
  viewport: {
    width: 1024,
    height: 625,
  },
  layout: {
    shell: 'Full page status surface',
    container: 'Centered status image, text, and primary action',
    stack: 'Image -> title/description -> action',
    responsive: ['desktop source frame for this pass'],
    relationships: [
      {
        from: 'Status image',
        to: 'Text group',
        figma: '36px vertical gap',
        code: 'gap-9',
      },
      {
        from: 'Title',
        to: 'Description',
        figma: '10px vertical gap',
        code: 'gap-2.5',
      },
    ],
  },
  data: {
    source: 'static',
    fixtures: ['STATUS_IMAGES.forbidden'],
    states: [
      {
        state: 'light',
        fixture: 'forbidden-security-light.png',
        expected: '라이트 테마 403 이미지와 중앙 정렬 텍스트/버튼을 표시합니다.',
      },
    ],
  },
  states: ['light'],
  reuse: [
    {
      figmaPart: 'Box Button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '기존 box-solid-primary Button으로 40px CTA를 표현합니다.',
    },
    {
      figmaPart: '403 illustration',
      checked: 'public/image/status/forbidden-security-light.png',
      decision: 'new-shared',
      reason: '라이트/다크 별도 PNG 에셋을 내려받아 테마에 따라 교체합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Text/Nomal/Normal',
      value: '#33363d',
      code: 'text-text-normal-normal',
      decision: 'matched',
    },
    {
      figma: 'Text/Nomal/Alternative',
      value: '#6d7882',
      code: 'text-text-normal-alternative',
      decision: 'matched',
    },
    {
      figma: 'gap/36',
      value: '36px',
      code: 'gap-9',
      decision: 'scale-mapped',
    },
  ],
  render: () => (
    <StatusPreview>
      <StatusErrorPage
        title="이 대화는 질문자 본인만 볼 수 있어요"
        description="다른 구성원의 대화 내용은 공개되지 않아요"
        image={STATUS_IMAGES.forbidden}
        primaryAction={{ label: 'Catch Up에서 직접 검색하기', href: '/' }}
      />
    </StatusPreview>
  ),
};

export const forbiddenStatusDarkFigmaCase: FigmaLabCase = {
  ...forbiddenStatusLightFigmaCase,
  id: 'status-forbidden-dark',
  state: 'dark',
  title: 'Status / 403 Dark',
  description: '권한이 없는 상태 화면의 다크 테마 이미지를 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-184227&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '10328:184227',
  },
  data: {
    source: 'static',
    fixtures: ['STATUS_IMAGES.forbidden'],
    states: [
      {
        state: 'dark',
        fixture: 'forbidden-security-dark.png',
        expected: '다크 테마 403 이미지와 중앙 정렬 텍스트/버튼을 표시합니다.',
      },
    ],
  },
  states: ['dark'],
  render: () => (
    <StatusPreview dark>
      <StatusErrorPage
        title="이 대화는 질문자 본인만 볼 수 있어요"
        description="다른 구성원의 대화 내용은 공개되지 않아요"
        image={STATUS_IMAGES.forbidden}
        primaryAction={{ label: 'Catch Up에서 직접 검색하기', href: '/' }}
      />
    </StatusPreview>
  ),
};

export const notFoundStatusLightFigmaCase: FigmaLabCase = {
  id: 'status-not-found-light',
  groupId: 'shared-status',
  owner: 'shared',
  component: 'StatusErrorPage',
  state: 'light',
  kind: 'page',
  title: 'Status / 404 Light',
  description: '루트 404 상태 화면의 라이트 테마 레이아웃을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-183838&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '10328:183838',
  },
  targetRoute: '/not-found',
  viewport: {
    width: 1024,
    height: 625,
  },
  layout: {
    shell: 'Root not-found surface',
    container: 'Centered status image, text, and two actions',
    stack: 'Image -> title/description -> previous/home actions',
    responsive: ['desktop source frame for this pass'],
    relationships: [
      {
        from: 'Status image',
        to: 'Text group',
        figma: '36px vertical gap',
        code: 'gap-9',
      },
      {
        from: 'Previous button',
        to: 'Home button',
        figma: '16px horizontal gap',
        code: 'gap-4',
      },
    ],
  },
  data: {
    source: 'static',
    fixtures: ['STATUS_IMAGES.notFound'],
    states: [
      {
        state: 'light',
        fixture: 'not-found-light.png',
        expected: '라이트 테마 404 이미지와 이전/홈 버튼을 표시합니다.',
      },
    ],
  },
  states: ['light'],
  reuse: [
    {
      figmaPart: 'Primary Box Button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '홈으로 돌아가기 CTA는 기존 box-solid-primary Button을 사용합니다.',
    },
    {
      figmaPart: 'Secondary Box Button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '이전 페이지 CTA는 기존 box-outline-gray Button을 사용합니다.',
    },
    {
      figmaPart: '404 illustration',
      checked: 'public/image/status/not-found-light.png',
      decision: 'new-shared',
      reason: '라이트/다크 별도 PNG 에셋을 내려받아 테마에 따라 교체합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Text/Nomal/Normal',
      value: '#33363d',
      code: 'text-text-normal-normal',
      decision: 'matched',
    },
    {
      figma: 'Line/Normal/Neutral',
      value: '#eaebec',
      code: 'box-outline-gray border-line-normal-neutral',
      decision: 'matched',
    },
    {
      figma: 'gap/16',
      value: '16px',
      code: 'gap-4',
      decision: 'scale-mapped',
    },
  ],
  render: () => (
    <StatusPreview>
      <StatusErrorPage
        title="찾으시는 페이지가 없어요"
        description="주소가 잘못되었거나, 페이지가 이동했을 수 있어요"
        image={STATUS_IMAGES.notFound}
        secondaryAction={{ label: '이전 페이지', action: 'back' }}
        primaryAction={{ label: '홈으로 돌아가기', href: '/' }}
      />
    </StatusPreview>
  ),
};

export const notFoundStatusDarkFigmaCase: FigmaLabCase = {
  ...notFoundStatusLightFigmaCase,
  id: 'status-not-found-dark',
  state: 'dark',
  title: 'Status / 404 Dark',
  description: '루트 404 상태 화면의 다크 테마 이미지를 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-184247&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '10328:184247',
  },
  data: {
    source: 'static',
    fixtures: ['STATUS_IMAGES.notFound'],
    states: [
      {
        state: 'dark',
        fixture: 'not-found-dark.png',
        expected: '다크 테마 404 이미지와 이전/홈 버튼을 표시합니다.',
      },
    ],
  },
  states: ['dark'],
  render: () => (
    <StatusPreview dark>
      <StatusErrorPage
        title="찾으시는 페이지가 없어요"
        description="주소가 잘못되었거나, 페이지가 이동했을 수 있어요"
        image={STATUS_IMAGES.notFound}
        secondaryAction={{ label: '이전 페이지', action: 'back' }}
        primaryAction={{ label: '홈으로 돌아가기', href: '/' }}
      />
    </StatusPreview>
  ),
};
