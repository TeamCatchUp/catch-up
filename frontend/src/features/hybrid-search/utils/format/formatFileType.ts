// 파일명 확장자 우선, 없으면 MIME 서브타입을 짧은 타입 라벨로 (예: "pdf").
// FileRow 의 파일 타입 표시용. 확장자·MIME 둘 다 없으면 null 반환.

export function formatFileType(name: string, contentType: string | undefined): string | null {
  const extMatch = /\.([a-z0-9]+)$/i.exec(name);
  if (extMatch) return extMatch[1].toLowerCase();

  const mime = contentType?.trim();
  if (!mime) return null;
  const subtype = mime.split('/')[1]?.split('+')[0];
  return subtype ? subtype.toLowerCase() : null;
}
