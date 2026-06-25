import Image from 'next/image';

interface HelpArticleImageProps {
  lightSrc: string;
  darkSrc?: string;
  alt: string;
}

export default function HelpArticleImage({ lightSrc, darkSrc, alt }: HelpArticleImageProps) {
  return (
    <div className="relative aspect-59/25 w-full max-w-130 overflow-hidden rounded-2xl">
      <Image src={lightSrc} alt={alt} fill className={darkSrc ? 'object-cover dark:hidden' : 'object-cover'} />
      {darkSrc && <Image src={darkSrc} alt={alt} fill className="hidden object-cover dark:block" />}
    </div>
  );
}
