import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { Route } from "next";
import {
  featureVisibilityConfig,
  getHiddenFeatureForUrl,
} from "@/lib/featureVisibility";

export async function getCurrentRequestUrlForFeatureVisibility(): Promise<URL | null> {
  const headersList = await headers();
  const pathname =
    headersList.get("x-nextjs-pathname") ||
    headersList.get("next-url") ||
    headersList.get("x-invoke-path");
  const search = headersList.get("x-nextjs-search") || "";

  if (pathname) {
    return new URL(`${pathname}${search}`, "http://localhost");
  }

  const url = headersList.get("url");
  if (!url) {
    return null;
  }

  try {
    return new URL(url);
  } catch {
    return null;
  }
}

export async function redirectIfCurrentFeatureIsHidden(): Promise<void> {
  const url = await getCurrentRequestUrlForFeatureVisibility();
  if (!url || getHiddenFeatureForUrl(url.pathname, url.searchParams) === null) {
    return;
  }

  if (featureVisibilityConfig.hiddenFeatureFallback === "404") {
    redirect("/404" as Route);
  }

  redirect("/app" as Route);
}
