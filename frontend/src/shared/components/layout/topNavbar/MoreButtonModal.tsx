'use client';

import { useState } from 'react';

import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Switch } from '@/shared/components/ui/switch';

import AddSmall from '/public/icons/icon/add_small.svg';
import Alarm from '/public/icons/icon/alarm.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import CloudCheck from '/public/icons/icon/cloud_check.svg';
import Error from '/public/icons/icon/error.svg';
import IconType from '/public/icons/icon/icon_type.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Storage from '/public/icons/icon/storage.svg';
import ConfluenceLogo from '/public/icons/logo/Counfluence.svg';
import GithubLogo from '/public/icons/logo/GitHub.svg';
import JiraLogo from '/public/icons/logo/Jira.svg';
import SlackLogo from '/public/icons/logo/Slack.svg';

const linkServices = [
  { key: 'Jira', label: 'Jira', Icon: JiraLogo },
  { key: 'Confluence', label: 'Confluence', Icon: ConfluenceLogo },
  { key: 'Github', label: 'Github', Icon: GithubLogo },
  { key: 'Slack', label: 'Slack', Icon: SlackLogo },
] as const;

type LinkService = (typeof linkServices)[number]['key'];

const alertItems = ['멘션', '인계자 설정', '인수자 설정', '미팅 1시간 전', '미팅 30분 전', '미팅 시작'] as const;
type AlertItem = (typeof alertItems)[number];

export function MoreButtonContent() {
  const today = new Date();

  const [linked, setLinked] = useState<Record<LinkService, boolean>>({
    Jira: true,
    Confluence: true,
    Github: false,
    Slack: false,
  });
  const [alerts, setAlerts] = useState<Record<AlertItem, boolean>>({
    멘션: true,
    '인계자 설정': true,
    '인수자 설정': false,
    '미팅 1시간 전': false,
    '미팅 30분 전': false,
    '미팅 시작': false,
  });

  const linkedList = linkServices.filter((s) => linked[s.key]);
  const alertList = alertItems.filter((a) => alerts[a]);

  return (
    <DropdownMenuContent
      align="end"
      sideOffset={6}
      className="flex w-63 flex-col gap-3 py-3"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      {/* 검색 입력 */}
      <div className="px-1.5">
        <input
          placeholder="검색어를 입력하세요."
          className="border-neutral-3 text-body-small placeholder-gray-30 h-10 w-full rounded-xl border px-3 py-2 transition-colors outline-none focus:border-blue-30 focus:bg-neutral-1 focus:caret-blue-30"
          onKeyDown={(e) => e.stopPropagation()}
        />
      </div>

      <div className="flex flex-col">
        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
          <AddSmall className="h-6 w-6 shrink-0 text-gray-50" />
          <span>새 인수인계 시작하기</span>
        </DropdownMenuItem>

        <DropdownMenuItem onSelect={(e) => e.preventDefault()} className="justify-between">
          <div className="flex items-center gap-2.5">
            <IconType className="h-6 w-6 shrink-0 text-gray-50" />
            <span>글자 크기</span>
          </div>
          <div className="text-body-xsmall flex items-center text-gray-50">
            <span>중간</span>
            <ArrowRight className="h-6 w-6 text-gray-30" />
          </div>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
          <Error className="h-6 w-6 shrink-0 text-gray-50" />
          <span>도움말</span>
        </DropdownMenuItem>

        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
          <Storage className="h-6 w-6 shrink-0 text-gray-50" />
          <span>버전 기록</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* 연결 서브메뉴 */}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="justify-between">
            <div className="flex items-center gap-2.5">
              <CloudCheck className="h-6 w-6 shrink-0 text-gray-50" />
              <span>연결</span>
            </div>
            <div className="text-body-xsmall flex items-center text-gray-50">
              {linkedList.length > 0 && (
                <span className="max-w-19.5 truncate">{linkedList.map((s) => s.label).join(', ')}</span>
              )}
              <ArrowRight className="h-6 w-6 text-gray-30" />
            </div>
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-63">
            {linkServices.map(({ key, label, Icon }) => (
              <DropdownMenuItem
                key={key}
                onSelect={(e) => e.preventDefault()}
                onClick={() => setLinked((prev) => ({ ...prev, [key]: !prev[key] }))}
                className="justify-between"
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5" />
                  <span>{label}</span>
                </div>
                <div className="text-body-xsmall flex items-center text-gray-50">
                  <span>{linked[key] ? '연동' : '미연동'}</span>
                  <ArrowRight className="h-6 w-6 text-gray-30" />
                </div>
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSeparator />

        {/* 알림받기 서브메뉴 */}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="justify-between">
            <div className="flex items-center gap-2.5">
              <Alarm className="h-6 w-6 shrink-0 text-gray-50" />
              <span>알림받기</span>
            </div>
            <div className="text-body-xsmall flex items-center text-gray-50">
              {alertList.length > 0 && (
                <span className="max-w-19.5 truncate">{alertList.join(', ')}</span>
              )}
              <ArrowRight className="h-6 w-6 text-gray-30" />
            </div>
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="w-63">
            {alertItems.map((item) => (
              <DropdownMenuItem
                key={item}
                onSelect={(e) => e.preventDefault()}
                className="justify-between"
              >
                <span>{item}</span>
                <Switch
                  checked={alerts[item]}
                  onCheckedChange={(checked) => setAlerts((prev) => ({ ...prev, [item]: checked }))}
                />
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSeparator />
      </div>

      {/* 동기화 날짜 */}
      <div className="text-label-xsmall flex h-10 items-center gap-2.5 px-2">
        <Rotate className="h-5 w-5 text-gray-30" />
        <span className="text-gray-50">
          {today.getFullYear()}년 {today.getMonth() + 1}월 {today.getDate()}일
        </span>
      </div>
    </DropdownMenuContent>
  );
}
