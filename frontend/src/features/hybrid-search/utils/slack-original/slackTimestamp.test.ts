import { describe, expect, it } from 'vitest';

import { formatSlackDateKey, formatSlackEditedLabel, formatSlackMessageTime, slackTsToDate } from './slackTimestamp';

describe('slackTimestamp', () => {
  it('converts Slack ts into a valid date', () => {
    expect(slackTsToDate('1779601372.378609')?.toISOString()).toBe('2026-05-24T05:42:52.378Z');
    expect(formatSlackDateKey('1779601372.378609')).toBe('2026-05-24T05:42:52.378Z');
  });

  it('formats visible labels and hides invalid values', () => {
    expect(formatSlackMessageTime('1779601372.378609')).toBe('02:42 PM');
    expect(formatSlackMessageTime('bad')).toBe('');
    expect(formatSlackEditedLabel(undefined)).toBe('');
    expect(formatSlackEditedLabel('1779601372.378609')).toBe('편집됨');
  });
});
