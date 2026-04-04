export const TONE_OPTIONS = [
  { value: 'formal', label: '딱딱하게' },
  { value: 'default', label: '기본값' },
  { value: 'friendly', label: '친근하게' },
] as const;

export const EMOJI_OPTIONS = [
  { value: 'low', label: '낮음' },
  { value: 'default', label: '기본값' },
  { value: 'high', label: '높음' },
] as const;

export type ToneValue = (typeof TONE_OPTIONS)[number]['value'];
export type EmojiValue = (typeof EMOJI_OPTIONS)[number]['value'];

export const MAX_INSTRUCTION_LENGTH = 1500;
