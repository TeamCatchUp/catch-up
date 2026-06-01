export function slackTsToDate(ts: string | undefined): Date | null {
  if (!ts) return null;

  const seconds = Number(ts);
  if (!Number.isFinite(seconds)) return null;

  return new Date(Math.floor(seconds * 1000));
}

export function formatSlackMessageTime(ts: string | undefined): string {
  const date = slackTsToDate(ts);
  if (!date) return '';

  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatSlackDateKey(ts: string | undefined): string {
  return slackTsToDate(ts)?.toISOString() ?? '';
}

export function formatSlackEditedLabel(ts: string | undefined): string {
  if (!slackTsToDate(ts)) return '';
  return '편집됨';
}
