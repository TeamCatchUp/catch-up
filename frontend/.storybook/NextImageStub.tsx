import type { CSSProperties, ImgHTMLAttributes } from 'react';

/** next/image가 static import에서 만들어내는 객체 형태 */
interface StaticImageData {
  src: string;
  width: number;
  height: number;
  blurDataURL?: string;
}

interface StaticRequire {
  default: StaticImageData;
}

type StaticImport = StaticImageData | StaticRequire;

interface NextImageStubProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'width' | 'height'> {
  src: string | StaticImport;
  alt: string;
  width?: number | string;
  height?: number | string;
  /** 아래 prop들은 next/image 전용이라 <img>에 넘기지 않고 버린다 */
  fill?: boolean;
  priority?: boolean;
  quality?: number;
  placeholder?: string;
  blurDataURL?: string;
  unoptimized?: boolean;
  loader?: unknown;
  sizes?: string;
  loading?: 'lazy' | 'eager';
  overrideSrc?: string;
}

/**
 * `public/`은 vite의 publicDir이자 Storybook staticDirs다.
 * `@/public/...` 임포트는 `/public/...`을 돌려주는데 실제 서빙 경로는 `/...`이라 그대로 쓰면 404다.
 */
const stripPublicPrefix = (url: string): string => (url.startsWith('/public/') ? url.slice('/public'.length) : url);

const resolveSrc = (src: string | StaticImport): string => {
  if (typeof src === 'string') return stripPublicPrefix(src);
  if ('default' in src) return stripPublicPrefix(src.default.src);
  return stripPublicPrefix(src.src);
};

/**
 * Storybook 전용 next/image 대체.
 *
 * `@storybook/nextjs-vite`의 `virtual:next-image`가 static import를 처리할 때
 * 절대 경로를 JS 문자열 리터럴에 그대로 박아 넣어, Windows 경로의 백슬래시가
 * 이스케이프 시퀀스로 해석된다(`C:\Users\fkgrk\frontend` → `C:Userskgrkrontend`).
 * 그래서 PNG를 static import 하는 컴포넌트는 스토리를 띄울 수 없다.
 *
 * `.storybook/main.ts`의 vite alias로 `next/image`를 이것으로 갈아끼운다.
 * 프로덕션 번들에는 들어가지 않는다.
 */
export default function NextImageStub({
  src,
  alt,
  fill,
  priority: _priority,
  quality: _quality,
  placeholder: _placeholder,
  blurDataURL: _blurDataURL,
  unoptimized: _unoptimized,
  loader: _loader,
  sizes: _sizes,
  overrideSrc: _overrideSrc,
  style,
  ...rest
}: NextImageStubProps) {
  const fillStyle: CSSProperties | undefined = fill
    ? { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', ...style }
    : style;

  // eslint-disable-next-line @next/next/no-img-element
  return <img {...rest} src={resolveSrc(src)} alt={alt} style={fillStyle} />;
}
