"use client";

import { useMemo, useState } from "react";
import type { Route } from "next";
import Link from "next/link";
import useSWR from "swr";
import * as SettingsLayouts from "@/layouts/settings-layouts";
import { Button, Text } from "@opal/components";
import { SvgPlus, SvgTrash } from "@opal/icons";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import {
  deleteExternalRetrievalSource,
  fetchExternalRetrievalSources,
} from "./lib";

const route = ADMIN_ROUTES.EXTERNAL_RETRIEVAL_SOURCES;

export default function Page() {
  const [query, setQuery] = useState("");
  const { data, error, mutate, isLoading } = useSWR(
    "/api/external-retrieval/sources",
    fetchExternalRetrievalSources
  );

  const sources = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return data ?? [];
    }
    return (data ?? []).filter((source) =>
      `${source.name} ${source.description ?? ""} ${source.endpoint}`
        .toLowerCase()
        .includes(normalizedQuery)
    );
  }, [data, query]);

  const handleDelete = async (id: number) => {
    await deleteExternalRetrievalSource(id);
    await mutate();
  };

  return (
    <SettingsLayouts.Root>
      <SettingsLayouts.Header icon={route.icon} title={route.title} divider>
        <Link href={"/admin/external-retrieval/new" as Route}>
          <Button icon={SvgPlus}>New Source</Button>
        </Link>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <input
              className="w-96 rounded border border-border bg-background px-3 py-2 text-sm outline-none focus:border-text-600"
              placeholder="Search sources"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div>
              <Text font="secondary-body" color="text-03">
                {`${sources.length} configured`}
              </Text>
            </div>
          </div>

          {isLoading && (
            <div>
              <Text>Loading external retrieval sources...</Text>
            </div>
          )}
          {error && (
            <div className="text-status-danger-05">
              <Text color="inherit">
                Failed to load external retrieval sources.
              </Text>
            </div>
          )}

          {!isLoading && !error && sources.length === 0 && (
            <div className="rounded border border-border bg-background p-8">
              <Text as="h2" font="heading-h3">
                No external retrieval sources
              </Text>
              <div className="pt-2">
                <Text color="text-03">
                  Create a source to query external HTTP retrieval endpoints
                  during search.
                </Text>
              </div>
            </div>
          )}

          {sources.length > 0 && (
            <div className="overflow-hidden rounded border border-border bg-background">
              <table className="w-full table-fixed text-left text-sm">
                <thead className="border-b border-border bg-background-neutral-02">
                  <tr>
                    <th className="w-[20%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Name
                      </Text>
                    </th>
                    <th className="w-[12%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Adapter
                      </Text>
                    </th>
                    <th className="w-[24%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Endpoint
                      </Text>
                    </th>
                    <th className="w-[10%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Enabled
                      </Text>
                    </th>
                    <th className="w-[18%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Document Sets
                      </Text>
                    </th>
                    <th className="w-[16%] px-4 py-3">
                      <Text font="secondary-body" color="text-03">
                        Actions
                      </Text>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <tr
                      key={source.id}
                      className="border-b border-border last:border-b-0"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={
                            `/admin/external-retrieval/${source.id}` as Route
                          }
                        >
                          <Text font="main-ui-action">{source.name}</Text>
                        </Link>
                        {source.description && (
                          <div className="pt-1 truncate">
                            <Text font="secondary-body" color="text-03">
                              {source.description}
                            </Text>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Text font="secondary-body">{source.adapter_type}</Text>
                      </td>
                      <td className="px-4 py-3">
                        <div className="truncate">
                          <Text font="secondary-body">{source.endpoint}</Text>
                        </div>
                        <div>
                          <Text font="secondary-body" color="text-03">
                            {`${source.timeout_ms}ms · ${source.max_results} results`}
                          </Text>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div
                          className={
                            source.enabled ? "text-status-success-05" : ""
                          }
                        >
                          <Text
                            font="secondary-body"
                            color={source.enabled ? "inherit" : "text-03"}
                          >
                            {source.enabled ? "Enabled" : "Disabled"}
                          </Text>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="truncate">
                          <Text font="secondary-body">
                            {source.document_sets
                              .map((set) => set.name)
                              .join(", ") || "None"}
                          </Text>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Link
                            href={
                              `/admin/external-retrieval/${source.id}/test` as Route
                            }
                          >
                            <Button prominence="secondary" size="sm">
                              Test
                            </Button>
                          </Link>
                          <Button
                            icon={SvgTrash}
                            prominence="tertiary"
                            size="sm"
                            onClick={() => handleDelete(source.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
