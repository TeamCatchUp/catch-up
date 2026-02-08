import { InputHTMLAttributes, ReactNode } from 'react';

export interface TextfieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** 라벨 텍스트 */
  label?: string;
  /** 필수 여부 (빨간 점 표시) */
  required?: boolean;
  /** 헬퍼 텍스트 */
  helperText?: string;
  /** 에러 메시지 (표시 시 에러 스타일 적용) */
  error?: string;
  /** 우측 아이콘/요소 */
  suffix?: ReactNode;
}
