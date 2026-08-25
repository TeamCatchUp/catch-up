import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewParticipantsCard from './ReviewParticipantsCard';

/** 추가 후보 기본값 — 멤버 목록에서 현 담당자를 뺀 나머지를 소비처가 실어 준다 */
const CANDIDATES = [
  { id: '2', label: '직원10' },
  { id: '3', label: '이진수' },
  { id: '6', label: '팀원G', suffixLabel: '(나)' },
];

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/ReviewParticipantsCard',
  component: ReviewParticipantsCard,
  tags: ['autodocs'],
  /** 우측 패널 폭(350) 슬롯을 흉내낸다 — 카드 자체는 px를 갖지 않는다 */
  decorators: [(Story) => <div className="w-87.5">{Story()}</div>],
  args: {
    participants: [],
    notice: null,
    canAssign: false,
    canRemove: false,
    candidates: CANDIDATES,
    onAssign: fn(),
    onRemove: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17564-127037',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17564:127037',
      },
      viewport: { width: 400, height: 480 },
      states: [
        'no-owner-as-admin',
        'no-owner-as-member',
        'me-as-owner',
        'other-owner-as-admin',
        'other-owner-as-member',
        'multiple-owners',
      ],
      reuseNotes: [
        'ReviewQueuePage 우측 패널의 담당자 카드다 — 행·툴팁의 확정 노드와 시각 근거는 ReviewQueuePage 스토리 노트에 있다.',
        'OwnerAddPopover(추가 드롭다운·확인 모달)·OwnerDetailPopover(해제)를 동봉해 조립만 한다.',
      ],
      dataNotes: [
        '판정(can_review)과 담당자 관리(can_manage_owners)는 다른 규칙이다 — 판정은 담당자가 있으면 담당자 본인만이고 없으면 구성원 누구나, 관리는 지정=관리자∨담당자 본인·해제=관리자만이다.',
        '이 카드는 그 판정을 재계산하지 않는다 — canAssign·canRemove·notice 전부 소비처(라우트)가 실어 준다.',
        '담당자 0명이면 행 목록이 빈다 — 판정 폴백이 구성원 전체라 특정인을 행으로 세울 근거가 없고, 배너가 상태를 말한다. 배너 문구는 시안 실측("채널 관리자가 검토")이 서버 규칙과 어긋나 사용자 확정 문구로 교체했다.',
      ],
      layoutNotes: ['폭은 우측 패널(350)이 준다 — 스토리 데코레이터가 그 슬롯을 흉내낸다.'],
    }),
  },
} satisfies Meta<typeof ReviewParticipantsCard>;

export default meta;
type Story = StoryObj<typeof ReviewParticipantsCard>;

/** 담당자 0명 · 내가 관리자 — 빈 목록 + 지정(+) 버튼 + "구성원 누구나" 배너. */
export const NoOwnerAsAdmin: Story = {
  args: { notice: 'no-owner', canAssign: true, canRemove: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const banner = canvas.getByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.');
    // 좁은 패널에서 2줄이 될 수 있는 문구다 — 한국어가 단어 중간에서 잘리지 않아야 한다
    await expect(banner).toHaveClass('break-keep', 'wrap-break-word');
    await expect(canvas.getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();
    // 행이 없어 '담당자' 텍스트는 카드 제목뿐이다 — 없는 담당자를 행으로 흉내내지 않는다
    await expect(canvas.getAllByText('담당자')).toHaveLength(1);
  },
};

/** 담당자 0명 · 일반 구성원 — 같은 배너, 지정 진입점조차 없다. */
export const NoOwnerAsMember: Story = {
  args: { notice: 'no-owner' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.')).toBeInTheDocument();
    // + 버튼도 행 팝오버도 없다 — 카드에 버튼이 하나도 서지 않는다
    await expect(canvas.queryByRole('button')).toBeNull();
  },
};

/** 내가 담당자 — 내 행(나)만 서고 배너가 없다. 담당자 본인은 지정만 열린다(해제는 관리자만). */
export const MeAsOwner: Story = {
  args: {
    participants: [{ id: '6', userId: 6, name: '팀원G', isMe: true }],
    canAssign: true,
    canRemove: false,
    candidates: CANDIDATES.filter((candidate) => candidate.id !== '6'),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('팀원G')).toBeInTheDocument();
    await expect(canvas.getByText('(나)')).toBeInTheDocument();
    await expect(canvas.queryByText('담당자가 검토할 문서입니다')).toBeNull();
    await expect(canvas.queryByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.')).toBeNull();
    await expect(canvas.getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();
    // 해제 권한이 없어 내 행은 팝오버 트리거가 아니다
    await expect(canvas.queryByRole('button', { name: /팀원G/ })).toBeNull();
  },
};

/** 남이 담당자 · 내가 관리자 — 그 사람 행 + 배너, 지정·해제 진입점이 모두 선다. */
export const OtherOwnerAsAdmin: Story = {
  args: {
    participants: [{ id: '1', userId: 1, name: '팀원F' }],
    notice: 'other-owner',
    canAssign: true,
    canRemove: true,
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await expect(canvas.getByText('담당자가 검토할 문서입니다')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();

    // 행을 열면 해제 팝오버가 서고, 해제하기가 대상 user_id를 내보낸다
    await userEvent.click(canvas.getByRole('button', { name: /팀원F/ }));
    await expect(await portal.findByText('팀원F 님이 이 문서의 검토 담당자입니다')).toBeInTheDocument();
    await userEvent.click(portal.getByRole('button', { name: '담당자 해제하기' }));
    await expect(args.onRemove).toHaveBeenCalledWith(1);
  },
};

/** 남이 담당자 · 일반 구성원 — 그 사람 행과 배너만 남고 관리 진입점이 없다. */
export const OtherOwnerAsMember: Story = {
  args: {
    participants: [{ id: '1', userId: 1, name: '팀원F' }],
    notice: 'other-owner',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('담당자가 검토할 문서입니다')).toBeInTheDocument();
    await expect(canvas.getByText('팀원F')).toBeInTheDocument();
    await expect(canvas.queryByRole('button')).toBeNull();
  },
};

/** 복수 담당자 — 행이 스택으로 서고, 해제 권한이 있으면 행마다 팝오버 트리거다. */
export const MultipleOwners: Story = {
  args: {
    participants: [
      { id: '1', userId: 1, name: '팀원F' },
      { id: '3', userId: 3, name: '이진수' },
      { id: '6', userId: 6, name: '팀원G', isMe: true },
    ],
    canAssign: true,
    canRemove: true,
    candidates: [{ id: '2', label: '직원10' }],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 담당자 태그가 행 수만큼 선다 — 카드 제목까지 더해 4다
    await expect(canvas.getAllByText('담당자')).toHaveLength(4);
    await expect(canvas.getByText('(나)')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /팀원F/ })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /이진수/ })).toBeInTheDocument();
  },
};
