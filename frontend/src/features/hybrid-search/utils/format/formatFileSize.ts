// 바이트 → 사람이 읽는 크기 문자열 (예: "347.3KB"). B 단위는 소수점 없이.
// FileRow 의 파일 크기 표시용. 음수·Infinity·null/undefined 는 null 반환.

const FILE_SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

export function formatFileSize(bytes: number | undefined): string | null {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return null;

  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < FILE_SIZE_UNITS.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  const rounded = unitIndex === 0 ? String(size) : size.toFixed(1);
  return `${rounded}${FILE_SIZE_UNITS[unitIndex]}`;
}
