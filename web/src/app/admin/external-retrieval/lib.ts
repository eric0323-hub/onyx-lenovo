import {
  ExternalRetrievalSourceSummary,
  ExternalRetrievalSourceUpsertRequest,
  ExternalRetrievalSourceView,
  ExternalRetrievalTestResult,
} from "./types";

const BASE_URL = "/api/external-retrieval";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function fetchExternalRetrievalSources() {
  const response = await fetch(`${BASE_URL}/sources`);
  return parseResponse<ExternalRetrievalSourceSummary[]>(response);
}

export async function fetchExternalRetrievalSource(id: number) {
  const response = await fetch(`${BASE_URL}/sources/${id}`);
  return parseResponse<ExternalRetrievalSourceView>(response);
}

export async function createExternalRetrievalSource(
  request: ExternalRetrievalSourceUpsertRequest
) {
  const response = await fetch(`${BASE_URL}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<ExternalRetrievalSourceView>(response);
}

export async function updateExternalRetrievalSource(
  id: number,
  request: Partial<ExternalRetrievalSourceUpsertRequest>
) {
  const response = await fetch(`${BASE_URL}/sources/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<ExternalRetrievalSourceView>(response);
}

export async function deleteExternalRetrievalSource(id: number) {
  const response = await fetch(`${BASE_URL}/sources/${id}`, {
    method: "DELETE",
  });
  return parseResponse<void>(response);
}

export async function testExternalRetrievalSource(
  id: number,
  query: string,
  limit: number,
  includeRawResponse: boolean
) {
  const response = await fetch(`${BASE_URL}/sources/${id}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit,
      include_raw_response: includeRawResponse,
    }),
  });
  return parseResponse<ExternalRetrievalTestResult>(response);
}

export async function testExternalRetrievalConfig(
  request: ExternalRetrievalSourceUpsertRequest,
  query: string,
  limit: number,
  includeRawResponse: boolean
) {
  const response = await fetch(`${BASE_URL}/sources/test-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...request,
      test: {
        query,
        limit,
        include_raw_response: includeRawResponse,
      },
    }),
  });
  return parseResponse<ExternalRetrievalTestResult>(response);
}
