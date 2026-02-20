/** sessionStorage에서 값 읽기 (SSR 안전) */
export const getFromSessionStorage = (key: string): string | null => {
  if (typeof window === 'undefined') return null;

  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
};

/** sessionStorage에 값 쓰기 (SSR 안전) */
export const setToSessionStorage = (key: string, value: string): void => {
  if (typeof window === 'undefined') return;

  try {
    sessionStorage.setItem(key, value);
  } catch (error) {
    console.warn(`Error writing to sessionStorage key "${key}":`, error);
  }
};

/** sessionStorage에서 값 삭제 (SSR 안전) */
export const removeFromSessionStorage = (key: string): void => {
  if (typeof window === 'undefined') return;

  try {
    sessionStorage.removeItem(key);
  } catch (error) {
    console.warn(`Error removing sessionStorage key "${key}":`, error);
  }
};
