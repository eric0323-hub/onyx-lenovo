const FALLBACK_TEXT_ENCODINGS = ["utf-8", "gb18030", "gbk", "big5"];

function normalizeHeaderValue(value: string): string {
  return value.trim().replace(/^"|"$/g, "");
}

function charsetFromContentType(contentType: string | null): string | null {
  if (!contentType) {
    return null;
  }

  const charsetPart = contentType
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.toLowerCase().startsWith("charset="));

  if (!charsetPart) {
    return null;
  }

  const charset = normalizeHeaderValue(charsetPart.split("=").slice(1).join("="));
  return charset || null;
}

export function fileNameFromContentDisposition(
  contentDisposition: string | null
): string | null {
  if (!contentDisposition) {
    return null;
  }

  const encodedMatch = contentDisposition.match(/filename\*\s*=\s*([^;]+)/i);
  if (encodedMatch?.[1]) {
    const encodedValue = normalizeHeaderValue(encodedMatch[1]);
    const encodedFileName = encodedValue.includes("''")
      ? encodedValue.split("''").slice(1).join("''")
      : encodedValue;
    try {
      return decodeURIComponent(encodedFileName);
    } catch {
      return encodedFileName;
    }
  }

  const plainMatch = contentDisposition.match(/filename\s*=\s*([^;]+)/i);
  if (plainMatch?.[1]) {
    return normalizeHeaderValue(plainMatch[1]).replace(/\\"/g, '"');
  }

  return null;
}

export async function readBlobAsTextWithFallback(
  blob: Blob,
  contentType: string | null
): Promise<string> {
  const bytes = await blob.arrayBuffer();
  const preferredEncoding = charsetFromContentType(contentType);
  const encodings = [
    ...(preferredEncoding ? [preferredEncoding] : []),
    ...FALLBACK_TEXT_ENCODINGS.filter(
      (encoding) => encoding.toLowerCase() !== preferredEncoding?.toLowerCase()
    ),
  ];

  for (const encoding of encodings) {
    try {
      return new TextDecoder(encoding, { fatal: true }).decode(bytes);
    } catch {
      // Try the next likely encoding.
    }
  }

  return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
}
