import { ReactNode } from 'react';

export interface DropdownProps<T> {
  /** 라벨 텍스트 */
  label?: string;
  /** 필수 여부 (빨간 점 표시) */
  required?: boolean;
  /** 현재 선택된 값 */
  value: T;
  /** 값 변경 핸들러 */
  onChange: (value: T) => void;
  /** 트리거에 표시할 텍스트 */
  displayValue?: string;
  /** placeholder (미선택 시) */
  placeholder?: string;
  /** 옵션 목록 */
  children: ReactNode;
  /** 추가 className */
  className?: string;
}

export interface DropdownOptionProps<T> {
  /** 옵션 값 */
  value: T;
  /** 옵션 텍스트 */
  children: ReactNode;
  /** 추가 className */
  className?: string;
}
