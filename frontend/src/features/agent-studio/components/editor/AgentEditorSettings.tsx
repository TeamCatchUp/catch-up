'use client';

import { useRouter } from 'next/navigation';

import ArrowBackIcon from '@/public/icons/icon/arrow_back.svg';
import ClockIcon from '@/public/icons/icon/clock.svg';
import HelpIcon from '@/public/icons/icon/help.svg';
import KebabHorizontalIcon from '@/public/icons/icon/kebab_horizontal.svg';
import TagIcon from '@/public/icons/icon/tag.svg';
import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';

import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../../fixtures/agentStudioFixtures';
import { useAgentEditorSettingsForm } from '../../hooks/useAgentEditorSettingsForm';
import AgentSettingSection from './AgentSettingSection';
import AgentInstructionField from './fields/AgentInstructionField';
import AgentSelectField from './fields/AgentSelectField';

export default function AgentEditorSettings() {
  const router = useRouter();
  const form = useAgentEditorSettingsForm();

  return (
    <main className="bg-fill-normal-assistive-dark flex h-full min-w-0 flex-1 flex-col overflow-y-auto">
      <header className="bg-fill-normal-assistive-dark sticky top-0 z-10 flex h-13 shrink-0 items-center justify-between px-6 py-2">
        <Button variant="icon-only-gray" size="md" aria-label="Agent Studio로 돌아가기" onClick={() => router.back()}>
          <ArrowBackIcon className="size-6" aria-hidden="true" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="icon-only-gray" size="md" aria-label="설정 더보기">
              <KebabHorizontalIcon className="size-6" aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <MoreButtonContent />
        </DropdownMenu>
      </header>
      <div className="flex min-w-0 flex-col items-start gap-8 px-9 pt-5 pb-9">
        <div className="flex w-full items-center gap-3">
          <h1 className="text-heading-xlarge text-text-normal-strong min-w-0 flex-1 truncate">설정</h1>
          <Button variant="box-solid-primary" size="lg" disabled={!form.canPublish} onClick={form.handlePublish}>
            배포하기
          </Button>
        </div>
        {form.isPublishError && (
          <p className="text-body-small text-status-destructive w-full">배포에 실패했습니다. 입력값을 확인해주세요.</p>
        )}

        <AgentSettingSection
          step={1}
          title="채널톡 문의 유입 감지"
          description="완성된 문의 대응 가이드라인을 전송할 메시지를 찾습니다."
        >
          <AgentSelectField
            required
            label="어떤 채널로 들어오는 문의를 감지할까요?"
            value={form.channelTalkSelect.value}
            placeholder={form.channelTalkSelect.placeholder}
            icon={<TagIcon className="size-5.5" aria-hidden="true" />}
            items={form.channelTalkSelect.items}
            disabled={form.channelTalkSelect.disabled}
            onChange={form.channelTalkSelect.onChange}
          />
          <AgentSelectField
            required
            label="고객의 마지막 문의 메시지가 들어온 후 몇 분 후에 Agent를 실행할까요?"
            value={form.quietPeriodSelect.value}
            icon={<ClockIcon className="size-5.5" aria-hidden="true" />}
            items={form.quietPeriodSelect.items}
            onChange={form.quietPeriodSelect.onChange}
          />
          <div className="bg-fill-normal-strong flex w-full flex-col items-start justify-center gap-1.5 rounded-xl px-4 py-3">
            <div className="flex w-full items-start gap-1.5">
              <HelpIcon className="text-icon-normal-neutral size-5 shrink-0" aria-hidden="true" />
              <p className="text-body-xsmall text-text-normal-neutral">왜 바로 만들지 않나요?</p>
            </div>
            <p className="text-body-xsmall text-text-normal-alternative w-full whitespace-pre-wrap">
              문의가 들어오자마자 초안을 만들면 상담사가 직접 대응할 수 있는 문의까지 불필요하게 초안이 쌓여요. 고객이
              문의를 보내는 동안 맥락이 충분히 모인 뒤에 초안을 만들어, 더 정확하게 도와드려요.
            </p>
          </div>
        </AgentSettingSection>

        <AgentSettingSection
          step={2}
          title="Slack으로 메시지 보내기"
          description="완성된 문의 대응 가이드라인을 전송할 메시지를 찾습니다."
        >
          <AgentSelectField
            required
            label="누구의 권한을 가지고 조회할까요?"
            value={form.slackCredentialSelect.value}
            placeholder={form.slackCredentialSelect.placeholder}
            items={form.slackCredentialSelect.items}
            disabled={form.slackCredentialSelect.disabled}
            onChange={form.slackCredentialSelect.onChange}
          />
          <AgentSelectField
            required
            label={
              <span>
                채널톡을 연동한 <span className="text-text-primary-normal">Slack</span> 채널을 선택해주세요.
              </span>
            }
            value={form.slackChannelSelect.value}
            placeholder={form.slackChannelSelect.placeholder}
            icon={<TagIcon className="size-5.5" aria-hidden="true" />}
            items={form.slackChannelSelect.items}
            disabled={form.slackChannelSelect.disabled}
            onChange={form.slackChannelSelect.onChange}
          />
          <AgentInstructionField
            value={form.instruction}
            onChange={form.setInstruction}
            maxLength={AGENT_STUDIO_SETTINGS_FIXTURE.instructionMaxLength}
            hintText={AGENT_STUDIO_SETTINGS_FIXTURE.instructionHintText}
          />
        </AgentSettingSection>
      </div>
    </main>
  );
}
