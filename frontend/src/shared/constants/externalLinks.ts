/**
 * CatchUp 운영팀 Slack Connect 초대 링크.
 * 초대 링크는 배포 환경변수로 주입한다.
 */
export const SLACK_CONNECT_URL = process.env.NEXT_PUBLIC_SLACK_CONNECT_URL ?? '';
