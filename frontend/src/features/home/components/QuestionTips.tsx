import Image from 'next/image';

import Book from '@/public/icons/icon/book.svg';

import { tipData } from '../constants/questionTips';

interface QuestionTipsProps {
  onTipClick: (index: number) => void;
}

// 2개씩 묶어서 행 생성
const rows = [tipData.slice(0, 2), tipData.slice(2, 4), tipData.slice(4, 6)];

const QuestionTips = ({ onTipClick }: QuestionTipsProps) => {
  return (
    <section className="flex w-268 flex-col gap-4">
      <header className="flex items-center gap-3">
        <div className="border-edge-neutral bg-fill-primary-assistive flex h-8 w-8 items-center justify-center rounded-lg border-[0.5px]">
          <Book className="h-6 w-6 text-icon-primary" />
        </div>
        <h2 className="text-heading-large text-content-normal">질문 작성을 도와드릴게요!</h2>
      </header>

      <div className="flex flex-col gap-3">
        {rows.map((row, rowIdx) => (
          <div key={rowIdx} className="flex gap-6">
            {row.map((tip, colIdx) => {
              const tipIndex = rowIdx * 2 + colIdx;
              return (
              <button
                key={colIdx}
                type="button"
                onClick={() => onTipClick(tipIndex)}
                className="border-edge-neutral flex flex-1 cursor-pointer items-center overflow-hidden rounded-xl border bg-fill-normal text-left"
              >
                <div className="flex flex-[1_0_0] flex-col gap-1.5 p-5">
                  <h3 className="text-heading-medium text-content-neutral">{tip.title}</h3>
                  <p className="text-body-small whitespace-pre-line text-content-alternative">{tip.description}</p>
                </div>
                <div className="relative aspect-260/118 flex-[1_0_0] overflow-hidden">
                  <Image src={tip.image} alt={tip.title} fill className="object-cover dark:hidden" />
                  <Image
                    src={tip.image.replace('/light/', '/dark/')}
                    alt={tip.title}
                    fill
                    className="hidden object-cover dark:block"
                  />
                </div>
              </button>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
};

export default QuestionTips;
