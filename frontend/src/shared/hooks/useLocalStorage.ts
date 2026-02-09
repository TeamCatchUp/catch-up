/**
 * localStorage 동기화 훅
 * SSR 환경에서 안전하게 localStorage를 사용
 */

'use client';

import { useCallback, useState } from 'react';

interface UseLocalStorageOptions<T> {
  /** localStorage 키 */
  key: string;
  /** 초기값 (localStorage에 값이 없을 때 사용) */
  initialValue: T;
  /** 값 직렬화 함수 (기본: JSON.stringify) */
  serialize?: (value: T) => string;
  /** 값 역직렬화 함수 (기본: JSON.parse) */
  deserialize?: (value: string) => T;
}

/** localStorage 동기화 훅 */
export const useLocalStorage = <T>({
  key,
  initialValue,
  serialize = JSON.stringify,
  deserialize = JSON.parse,
}: UseLocalStorageOptions<T>): [T, (value: T | ((prev: T) => T)) => void, () => void] => {
  // SSR에서는 initialValue 사용, 클라이언트에서 실제 값으로 업데이트
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return initialValue;
    }

    try {
      const item = localStorage.getItem(key);
      return item ? deserialize(item) : initialValue;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  // key 변경 시 localStorage 재동기화 (adjusting state during render)
  const [prevKey, setPrevKey] = useState(key);
  if (prevKey !== key) {
    setPrevKey(key);
    try {
      const item = typeof window !== 'undefined' ? localStorage.getItem(key) : null;
      setStoredValue(item ? deserialize(item) : initialValue);
    } catch {
      setStoredValue(initialValue);
    }
  }

  // 값 설정 함수
  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        // 함수형 업데이트 지원
        const valueToStore = value instanceof Function ? value(storedValue) : value;
        setStoredValue(valueToStore);

        if (typeof window !== 'undefined') {
          localStorage.setItem(key, serialize(valueToStore));
        }
      } catch (error) {
        console.warn(`Error setting localStorage key "${key}":`, error);
      }
    },
    [key, storedValue, serialize],
  );

  // 값 삭제 함수
  const removeValue = useCallback(() => {
    try {
      setStoredValue(initialValue);
      if (typeof window !== 'undefined') {
        localStorage.removeItem(key);
      }
    } catch (error) {
      console.warn(`Error removing localStorage key "${key}":`, error);
    }
  }, [key, initialValue]);

  return [storedValue, setValue, removeValue];
};

/** localStorage에서 값 읽기 (SSR 안전) */
export const getFromLocalStorage = <T>(key: string, defaultValue: T): T => {
  if (typeof window === 'undefined') return defaultValue;

  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
};

/** localStorage에 값 쓰기 (SSR 안전) */
export const setToLocalStorage = <T>(key: string, value: T): void => {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Error writing to localStorage key "${key}":`, error);
  }
};

export default useLocalStorage;
