import type { ReactNode } from 'react';

import {
  HelpArticleEmphasis,
  HelpArticleQuote,
  HelpArticleSection,
  HelpArticleStep,
  HelpArticleSubsection,
  HelpArticleText,
} from '@/features/mypage/help/components/article/HelpArticleBlocks';
import HelpCommandBlock from '@/features/mypage/help/components/article/HelpCommandBlock';
import McpScriptCommands from '@/features/mypage/help/components/article/McpScriptCommands';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';
import ArrowForwardIcon from '@/public/icons/icon/arrow_circle_right.svg';
import ArrowOutwardIcon from '@/public/icons/icon/arrow_outward.svg';
import ClaudeIcon from '@/public/icons/logo/claude.svg';
import { Button } from '@/shared/components/ui/button';
import { SLACK_CONNECT_URL } from '@/shared/constants/externalLinks';

export const TUTORIAL_4_SECTIONS = [
  { id: 'what-is-mcp', title: 'Catch Up MCP가 뭔가요?' },
  { id: 'before-install', title: '설치 전 확인해주세요' },
  { id: 'before-use', title: '사용 전 꼭 확인해주세요' },
  { id: 'claude-desktop', title: 'Claude Desktop에 설치하기' },
  { id: 'claude-code', title: 'Claude Code에 설치하기' },
  { id: 'delete-mcp', title: '삭제하기' },
  { id: 'disable-claude-code', title: 'Claude Code에서 비활성화하기' },
  { id: 'manual-install', title: '수동 설치 방법' },
  { id: 'troubleshooting', title: '문제가 생겼나요?' },
] as const satisfies readonly HelpArticleNavItem[];

export const TUTORIAL_4_NAV_ITEMS = [
  TUTORIAL_4_SECTIONS[0],
  TUTORIAL_4_SECTIONS[1],
  TUTORIAL_4_SECTIONS[2],
  TUTORIAL_4_SECTIONS[3],
  TUTORIAL_4_SECTIONS[4],
  TUTORIAL_4_SECTIONS[7],
  TUTORIAL_4_SECTIONS[8],
] as const satisfies readonly HelpArticleNavItem[];

const NODE_WINDOWS_INSTALL_COMMAND = 'winget install -e --id OpenJS.NodeJS';
const NODE_MAC_INSTALL_COMMAND = 'brew install node@24';
const NODE_VERSION_COMMAND = 'node --version  # 예) v24.17.0';

function ClaudeDownloadCard() {
  return (
    <a
      href="https://claude.com/download"
      target="_blank"
      rel="noreferrer"
      className="border-line-normal-neutral bg-fill-normal-normal flex w-full max-w-130 items-center gap-4 rounded-xl border p-3"
    >
      <ClaudeIcon aria-hidden className="size-10 shrink-0" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2.5">
          <span className="text-reading-body-md-small text-text-normal-normal">Claude</span>
          <span className="bg-fill-normal-interaction-hover rounded-md2 flex size-5.5 items-center justify-center">
            <ArrowOutwardIcon className="text-icon-normal-normal size-4.5" />
          </span>
        </span>
        <span className="text-label-xsmall text-text-normal-alternative truncate">https://claude.com/download</span>
      </span>
    </a>
  );
}

function SlackInquiryButton() {
  return (
    <Button variant="text-primary-blue" size="md" className="text-text-primary-normal gap-1 self-start" asChild>
      <a href={SLACK_CONNECT_URL} target="_blank" rel="noopener noreferrer">
        Slack으로 문의하기
        <ArrowForwardIcon className="size-5 shrink-0" />
      </a>
    </Button>
  );
}

function TroubleshootingSubsection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <HelpArticleSubsection title={title} titleVariant="reading-large" className="gap-4">
      {children}
    </HelpArticleSubsection>
  );
}

export default function Tutorial4Content() {
  return (
    <>
      <HelpArticleSection {...TUTORIAL_4_SECTIONS[0]}>
        <HelpArticleText className="flex flex-col gap-4 whitespace-pre-wrap">
          <p>Catch Up MCP는 평소에 쓰던 AI Agent가 회사 안의 업무 맥락을 직접 찾아볼 수 있게 해주는 연결 도구입니다.</p>
          <p>
            Slack, Jira, Confluence, GitHub, ChannelTalk에 흩어져 있는 자료를 AI Agent가 한 번에 검색할 수 있어요. 우리
            팀이 어떤 결정을 했는지, 어떤 이슈가 있었는지, 어떤 논의가 오갔는지까지 맥락을 이해하고 답변합니다.
          </p>
          <p>
            여러 서비스를 각각 연결할 필요는 없습니다.
            <br />
            <HelpArticleEmphasis>Catch Up MCP</HelpArticleEmphasis> 하나만 설치하면, 여러 업무 도구의 정보를 한 번에
            탐색할 수 있습니다.
          </p>
          <p>
            Catch Up은 사전에 인덱싱된 데이터를 기반으로 검색하기 때문에, 정확한 키워드를 몰라도 괜찮습니다.
            <br />
            “그때 논의했던 내용”, “이 기능이 왜 이렇게 바뀌었는지”, “비슷한 이슈가 있었는지”처럼 자연스럽게 물어봐도
            관련 맥락을 빠르게 찾아줍니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[1]}>
        <HelpArticleText className="flex flex-col gap-4">
          <p className="text-reading-heading-sb-medium">설치하기 전에 아래 항목을 먼저 확인해주세요.</p>
          <ul className="list-disc pl-6">
            <li>사내 VPN에 연결되어 있어야 합니다.</li>
            <li>Catch Up에 회원가입된 사용자만 이용할 수 있습니다.</li>
            <li>회사 SSO 계정으로 로그인할 수 있어야 합니다.</li>
            <li>
              Catch Up MCP는 <HelpArticleEmphasis>Claude Desktop</HelpArticleEmphasis> 또는{' '}
              <HelpArticleEmphasis>Claude Code</HelpArticleEmphasis>에서 사용할 수 있습니다.
            </li>
          </ul>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[2]}>
        <HelpArticleText className="flex flex-col gap-4">
          <p>
            Catch Up MCP는 <HelpArticleEmphasis>Claude Desktop</HelpArticleEmphasis>과{' '}
            <HelpArticleEmphasis>Claude Code</HelpArticleEmphasis>에서 사용할 수 있습니다.
          </p>
          <p>
            <HelpArticleEmphasis>웹 브라우저 화면에서는 사용할 수 없습니다.</HelpArticleEmphasis>
            <br />
            보안 정책으로 인해 VPN 환경에서만 동작하기 때문에 웹에서는 사용할 수 없습니다.
            <br />
            브라우저에서 Claude를 사용 중이라면, 먼저 Claude Desktop을 설치한 뒤 아래 안내에 따라 Catch Up MCP를
            연결해주세요.
          </p>
        </HelpArticleText>
        <ClaudeDownloadCard />
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[3]}>
        <div className="flex flex-col gap-8">
          <HelpArticleStep order={1} title="Claude Desktop에 설치하기">
            <HelpArticleText>
              <p>Claude Desktop이 아직 없다면 먼저 설치해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={2} title="설치 명령어 복사하기">
            <HelpArticleText>
              <p>Catch Up 서비스에 접속한 뒤 아래 경로로 이동합니다.</p>
              <p>
                <HelpArticleEmphasis>우측 상단 프로필 → MCP 설치</HelpArticleEmphasis>
              </p>
              <p>사용 중인 운영체제에 맞는 명령어를 복사해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep title="Mac">
            <HelpArticleText>
              <p>터미널을 열고, 복사한 명령어를 붙여넣은 뒤 Enter를 누릅니다.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['mac']} showHeader={false} />
          </HelpArticleStep>

          <HelpArticleStep title="Windows">
            <HelpArticleText>
              <p>PowerShell을 열고, 복사한 명령어를 붙여넣은 뒤 Enter를 누릅니다.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['windows']} showHeader={false} />
          </HelpArticleStep>

          <HelpArticleStep order={3} title="Claude Desktop 재시작하기">
            <HelpArticleText>
              <p>설치가 끝나면 Claude Desktop을 완전히 종료한 뒤 다시 실행해주세요.</p>
              <p>단순히 창만 닫는 것이 아니라, 시스템 트레이에서 앱을 완전히 종료해야 합니다.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={4} title="SSO 로그인하기">
            <HelpArticleText>
              <p>
                Claude Desktop을 다시 실행하면 SSO 로그인 화면이 열립니다.
                <br />
                회사 계정으로 로그인해주세요.
              </p>
              <p>로그인이 완료되면 Catch Up MCP 연결이 활성화됩니다.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={5} title="연결 확인하기">
            <HelpArticleText>
              <p>Claude Desktop 채팅창에 아래처럼 입력해보세요.</p>
            </HelpArticleText>
            <HelpArticleQuote>
              <p>Catch Up 연결됐어?</p>
            </HelpArticleQuote>
            <HelpArticleText>
              <p>또는 Claude Desktop 설정에서 커넥터 목록에 Catch Up이 표시되는지 확인할 수 있습니다.</p>
            </HelpArticleText>
          </HelpArticleStep>
        </div>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[4]}>
        <div className="flex flex-col gap-3">
          <HelpArticleText>
            <p>터미널에서 아래 명령어를 실행합니다.</p>
          </HelpArticleText>
          <McpScriptCommands scriptKeys={['claude_code']} showHeader={false} />
          <HelpArticleText>
            <p>설치 후 Claude Code에서 아래 순서로 인증을 진행합니다.</p>
          </HelpArticleText>
        </div>
        <HelpArticleText>
          <ol className="list-decimal pl-6">
            <li>/mcp 입력</li>
            <li>catch-up 선택</li>
            <li>Authenticate 선택</li>
            <li>인증 URL 접속</li>
            <li>회사 계정으로 SSO 로그인</li>
            <li>인증 완료</li>
          </ol>
          <p>인증이 끝나면 Claude Code에서 Catch Up MCP를 사용할 수 있습니다.</p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[5]}>
        <HelpArticleSubsection title="Claude Desktop에서 삭제하기" titleVariant="reading-large" className="gap-4">
          <HelpArticleText>
            <p>
              Claude Desktop에서 아래 경로로 이동합니다.
              <br />
              설정 → 커넥터 → 데스크탑 → Catch Up → 제거
            </p>
          </HelpArticleText>
        </HelpArticleSubsection>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[6]}>
        <HelpArticleText>
          <p>Claude Code에서 아래 순서로 진행합니다.</p>
        </HelpArticleText>
        <HelpArticleText>
          <ol className="list-decimal pl-6">
            <li>/mcp 입력</li>
            <li>catch-up 선택</li>
            <li>Disable 선택</li>
          </ol>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[7]}>
        <div className="flex flex-col gap-4">
          <h3 className="text-heading-xlarge text-text-normal-normal">Claude Desktop</h3>
          <HelpArticleText>
            <ol className="list-decimal pl-6">
              <li>Node.js를 설치합니다.</li>
            </ol>
          </HelpArticleText>

          <HelpArticleStep title="Window">
            <HelpCommandBlock value={NODE_WINDOWS_INSTALL_COMMAND} ariaLabel="Windows Node.js 설치 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleStep title="Mac">
            <HelpCommandBlock value={NODE_MAC_INSTALL_COMMAND} ariaLabel="Mac Node.js 설치 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleStep title="설치 상태 확인">
            <HelpCommandBlock value={NODE_VERSION_COMMAND} ariaLabel="Node.js 설치 상태 확인 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleText>
            <ol className="list-decimal pl-6" start={2}>
              <li>Claude Desktop을 실행합니다.</li>
              <li>설정 &gt; 개발자 탭을 선택합니다.</li>
              <li>‘구성 편집’ 버튼을 선택합니다.</li>
              <li>파일 탐색기가 열리면 claude_desktop_config.json 파일을 안전한 장소에 백업합니다.</li>
              <li>해당 파일을 열어 아래와 같이 편집합니다.</li>
            </ol>
          </HelpArticleText>

          <McpScriptCommands scriptKeys={['claude_desktop_config']} showHeader={false} />

          <HelpArticleText>
            <ol className="list-decimal pl-6" start={6}>
              <li>Claude Desktop을 완전히 종료하고 재시작합니다.</li>
              <li>잠시 뒤 SSO 인증 화면이 팝업되며 로그인을 진행합니다.</li>
              <li>커넥터 목록 또는 Claude를 통해 Catch Up MCP 사용 가능 여부를 확인합니다.</li>
            </ol>
          </HelpArticleText>
        </div>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[8]} className="gap-3">
        <HelpArticleText>
          <p>아래 내용을 순서대로 확인해주세요.</p>
        </HelpArticleText>

        <div className="flex flex-col gap-8">
          <TroubleshootingSubsection title="SSO 로그인 화면이 뜨지 않아요">
            <HelpArticleText>
              <p>
                먼저 Claude Desktop을 완전히 종료한 뒤 다시 실행해주세요.
                <br />
                창만 닫으면 앱이 백그라운드에서 계속 실행 중일 수 있습니다.
              </p>
              <p>그래도 로그인 화면이 뜨지 않는다면 아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>설치 명령어를 운영체제에 맞게 실행했는지 확인해주세요.</li>
                <li>Claude Desktop 설정의 커넥터 목록에 Catch Up이 표시되는지 확인해주세요.</li>
              </ul>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="Catch Up이 커넥터 목록에 보이지 않아요">
            <HelpArticleText>
              <p>설치가 정상적으로 끝나지 않았을 수 있습니다.</p>
              <p>아래 순서대로 다시 시도해주세요.</p>
              <ol className="list-decimal pl-6">
                <li>Claude Desktop을 완전히 종료합니다.</li>
                <li>Catch Up 서비스에서 운영체제에 맞는 설치 명령어를 다시 복사합니다.</li>
                <li>터미널 또는 PowerShell에서 명령어를 다시 실행합니다.</li>
                <li>Claude Desktop을 다시 실행합니다.</li>
                <li>설정에서 커넥터 목록을 확인합니다.</li>
              </ol>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="“Catch Up 연결됐어?”라고 물어봐도 연결되지 않았다고 나와요">
            <HelpArticleText>
              <p>인증이 완료되지 않았거나, Claude Desktop이 설치 내용을 아직 반영하지 못했을 수 있습니다.</p>
              <p>아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>SSO 로그인을 완료했는지 확인해주세요.</li>
                <li>Claude Desktop을 완전히 종료 후 다시 실행해주세요.</li>
                <li>사내 VPN에 연결되어 있는지 확인해주세요.</li>
                <li>회사 계정에 Catch Up 사용 권한이 있는지 확인해주세요.</li>
              </ul>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="검색 결과가 없거나, 원하는 자료를 찾지 못해요">
            <HelpArticleText>
              <p>전사에 공개된 정보만 선별해 임베딩되어 있기 때문에, 일부 자료는 검색되지 않을 수 있습니다.</p>
              <br />
              <p>
                예를 들어, 특정 팀만 접근 가능한 Slack 채널, Jira 프로젝트, Confluence 페이지, GitHub 저장소의 내용은
                현재 검색 대상에 포함되어 있지 않습니다.
              </p>
              <p>또한 최근에 생성된 자료는 인덱싱이 완료되기 전까지 검색 결과에 바로 나오지 않을 수 있습니다.</p>
              <p>이럴 때는 질문을 조금 더 구체적으로 바꿔보면 도움이 될 수 있습니다.</p>
              <br />
              <p>예를 들어,</p>
              <p>
                “지난주 결제 오류 관련해서 논의된 내용 찾아줘” 처럼 너무 넓게 물어보면 관련 자료를 찾기 어려울 수
                있습니다.
              </p>
              <p>데이터가 충분히 쌓여 있다면,</p>
              <p>
                <span className="text-reading-heading-sb-small">
                  “지난주 Slack과 Jira에서 논의된 결제 실패 이슈의 원인과 결정사항을 정리해줘”
                </span>{' '}
                처럼 조금 더 구체적으로 물어봤을 때 더 정확한 결과를 얻을 수 있습니다.
              </p>
              <p>다만 현재는 일부 데이터만 연결되어 있을 수 있어, 원하는 결과가 충분히 나오지 않을 수도 있습니다.</p>
              <br />
              <p>
                전사 데이터를 순차적으로 확장하고 있으니, 조금만 기다려주시면 더 풍부한 맥락으로 답변을 받을 수
                있습니다.
              </p>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="VPN에 연결했는데도 동작하지 않아요">
            <HelpArticleText>
              <p>VPN 연결이 불안정하거나, 회사 네트워크에서 MCP 서버에 접근하지 못하는 상태일 수 있습니다.</p>
              <p>아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>VPN 연결 해제 후 다시 연결해주세요.</li>
                <li>브라우저에서 Catch Up 서비스에 접속되는지 확인해주세요.</li>
                <li>다른 네트워크를 사용 중이라면 회사에서 허용한 네트워크인지 확인해주세요.</li>
                <li>계속 동작하지 않으면 사내 관리자에게 문의해주세요.</li>
              </ul>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="Mac에서 설치 명령어가 실행되지 않아요">
            <HelpArticleText>
              <p>
                터미널에서 명령어를 실행했는지 확인해주세요.
                <br />
                명령어를 붙여넣을 때 따옴표나 공백이 바뀌면 실행되지 않을 수 있습니다.
              </p>
              <p>다시 복사해서 실행해도 실패한다면 아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>인터넷 연결 상태</li>
                <li>사내 VPN 연결 상태</li>
                <li>Catch Up 서비스 접속 가능 여부</li>
                <li>터미널에 표시된 오류 메시지</li>
              </ul>
              <p>오류 메시지를 함께 전달하면 더 빠르게 확인할 수 있습니다.</p>
              <p>문제 해결이 어렵다면 아래 Slack Connect 채널로 문의해주세요.</p>
            </HelpArticleText>
            <SlackInquiryButton />
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="Windows에서 PowerShell 실행이 막혀요">
            <HelpArticleText>
              <p>
                PowerShell을 사용하고 있는지 먼저 확인해주세요.
                <br />
                명령 프롬프트(cmd)가 아니라 PowerShell에서 실행해야 합니다.
              </p>
              <p>
                보안 정책 때문에 실행이 제한될 수 있습니다.
                <br />
                제공된 설치 명령어에는 일회성 실행 권한 설정이 포함되어 있지만, 회사 보안 정책에 따라 추가 제한이 있을
                수 있습니다.
              </p>
              <p>이 경우 사내 관리자에게 PowerShell 오류 메시지를 전달해주세요.</p>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="Claude Code에서 catch-up이 보이지 않아요">
            <HelpArticleText>
              <p>설치 명령어가 정상적으로 등록되지 않았을 수 있습니다.</p>
              <p>아래 명령어를 다시 실행해주세요.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['claude_code']} showHeader={false} />
            <HelpArticleText>
              <p>그다음 Claude Code에서 /mcp를 입력하고 catch-up이 표시되는지 확인해주세요.</p>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="Claude.ai에서 Catch Up이 로드되지 않아요.">
            <HelpArticleText>
              <p>
                Catch Up MCP는 현재 Claude Desktop과 Claude Code에서만 사용할 수 있습니다.
                <br />
                <a href="http://claude.ai/" target="_blank" rel="noreferrer" className="underline">
                  http://claude.ai
                </a>{' '}
                웹 브라우저에서는 MCP 서버의 도구가 로드되지 않습니다.
              </p>
              <p>
                브라우저에서 Claude를 사용 중이라면 Claude Desktop을 설치한 뒤, 이 문서의 Claude Desktop에 설치하기
                안내를 따라주세요.
              </p>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <TroubleshootingSubsection title="인증 URL에 접속했는데 인증이 실패해요">
            <HelpArticleText>
              <p>아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>회사 SSO 계정으로 로그인했는지 확인해주세요.</li>
                <li>Catch Up에 회원가입된 사용자 계정인지 확인해주세요.</li>
                <li>사내 VPN에 연결되어 있는지 확인해주세요.</li>
                <li>인증 URL이 만료되었다면 Claude에서 다시 Authenticate를 눌러 새 URL로 접속해주세요.</li>
              </ul>
            </HelpArticleText>
          </TroubleshootingSubsection>

          <div className="flex flex-col gap-3">
            <h3 className="text-heading-xlarge text-text-normal-normal">계속 해결되지 않는다면</h3>
            <HelpArticleText>
              <p>문제가 계속되면 아래 정보를 함께 전달해주세요.</p>
              <ul className="list-disc pl-6">
                <li>사용 중인 환경: Mac / Windows / Claude Desktop / Claude Code</li>
                <li>실행한 설치 명령어</li>
                <li>오류가 발생한 단계</li>
                <li>화면에 표시된 오류 메시지</li>
                <li>VPN 연결 여부</li>
                <li>Catch Up 서비스 접속 가능 여부</li>
              </ul>
              <p>이 정보를 함께 보내주시면 원인을 더 빠르게 확인할 수 있습니다.</p>
            </HelpArticleText>
          </div>
        </div>
      </HelpArticleSection>
    </>
  );
}
