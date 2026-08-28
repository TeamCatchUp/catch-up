interface ConnectorErrorNoticeProps {
  /** INTEGRATION_ACCOUNTS의 name — 'Jira' | 'Github' | 'Slack' | 'Confluence' | '채널톡' */
  serviceName: string;
}

/**
 * 커넥터 조회 실패 안내.
 * fetch 실패를 "연동된 항목이 없습니다."로 렌더하면 관리자가 연동 유실로 오해하므로 명시적으로 알린다.
 * 카피는 ChannelTalkManagementPanel의 현행 문구에서 도구명만 파라미터화한 것이다 — 새 문구가 아니다.
 */
export default function ConnectorErrorNotice({ serviceName }: ConnectorErrorNoticeProps) {
  return (
    <div className="flex flex-col gap-6">
      <div
        role="alert"
        className="border-line-normal-assistive bg-fill-normal-strong text-body-small text-status-destructive rounded-xl border px-4 py-3"
      >
        {serviceName} 연동 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
      </div>
    </div>
  );
}
