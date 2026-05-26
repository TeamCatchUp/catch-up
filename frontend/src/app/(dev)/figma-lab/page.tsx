import FigmaLabRenderer from './_registry/FigmaLabRenderer';

interface PageProps {
  searchParams: Promise<{
    case?: string;
  }>;
}

export default async function FigmaLabPage({ searchParams }: PageProps) {
  const params = await searchParams;

  return <FigmaLabRenderer selectedCaseId={params.case} />;
}
