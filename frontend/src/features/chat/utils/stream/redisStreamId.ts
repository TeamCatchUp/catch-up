const parseRedisStreamId = (id: string): [number, number] => {
  const [ms, seq] = id.split('-');
  return [Number(ms), Number(seq)];
};

export const compareRedisStreamIds = (a: string, b: string): number => {
  const [aMs, aSeq] = parseRedisStreamId(a);
  const [bMs, bSeq] = parseRedisStreamId(b);

  if (aMs !== bMs) return aMs - bMs;

  return aSeq - bSeq;
};

export const isRedisStreamIdAtOrBefore = (id: string | undefined, cutoffId: string | null): boolean => {
  if (!id || !cutoffId) return false;

  return compareRedisStreamIds(id, cutoffId) <= 0;
};
