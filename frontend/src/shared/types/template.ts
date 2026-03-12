export interface TemplateField {
  key: string;
  placeholder: string;
}

export type TemplateSegment = string | { field: string };

export interface TipData {
  title: string;
  description: string;
  image: string;
  template: TemplateSegment[];
  fields: TemplateField[];
}

export const buildQueryFromTemplate = (
  template: TemplateSegment[],
  fieldValues: Record<string, string>,
): string => template.map((seg) => (typeof seg === 'string' ? seg : fieldValues[seg.field] ?? '')).join('');
