'use client';

import { useState } from 'react';

import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from '@/shared/components/ui/dropdown-menu';

import ArrowRight from '/public/icons/icon/arrow_right.svg';
import CloudCheck from '/public/icons/icon/cloud_check.svg';
import Error from '/public/icons/icon/error.svg';
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

export function MoreButtonContent() {
  const [linked, setLinked] = useState<Record<LinkService, boolean>>({
    Jira: true,
    Confluence: true,
    Github: false,
    Slack: false,
  });

  const linkedList = linkServices.filter((s) => linked[s.key]);

  return (
    <DropdownMenuContent
      align="end"
      sideOffset={6}
      className="flex w-[250px] flex-col gap-1 rounded-xl"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <Error className="h-6 w-6 shrink-0 text-gray-50" />
        <span>도움말</span>
      </DropdownMenuItem>

      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <Storage className="h-6 w-6 shrink-0 text-gray-50" />
        <span>버전 기록</span>
      </DropdownMenuItem>

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
        <DropdownMenuSubContent className="w-[250px]">
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
    </DropdownMenuContent>
  );
}
