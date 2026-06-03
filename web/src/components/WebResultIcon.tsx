"use client";

import { ValidSources } from "@/lib/types";
import { SourceIcon } from "./SourceIcon";
import { useState } from "react";
import { SvgOnyxLogo, SvgGithub } from "@opal/logos";
import { APP_MARKETING_URL } from "@/lib/constants";

function getHostname(url: string) {
  if (!url) return "";
  try {
    return new URL(url).hostname;
  } catch {
    try {
      return new URL(`https://${url}`).hostname;
    } catch {
      return "";
    }
  }
}

const APP_MARKETING_HOSTNAME = getHostname(APP_MARKETING_URL);

export function WebResultIcon({
  url,
  size = 18,
}: {
  url: string;
  size?: number;
}) {
  const [error, setError] = useState(false);
  const hostname = getHostname(url);

  return (
    <>
      {APP_MARKETING_HOSTNAME && hostname.includes(APP_MARKETING_HOSTNAME) ? (
        <SvgOnyxLogo size={size} className="dark:text-white text-black" />
      ) : hostname === "github.com" || hostname.endsWith(".github.com") ? (
        <SvgGithub size={size} />
      ) : hostname && !error ? (
        <img
          className="my-0 rounded-full py-0"
          src={`https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${hostname}&size=128`}
          alt="favicon"
          height={size}
          onError={() => setError(true)}
          width={size}
          style={{
            height: `${size}px`,
            width: `${size}px`,
            background: "transparent",
          }}
        />
      ) : (
        <SourceIcon sourceType={ValidSources.Web} iconSize={size} />
      )}
    </>
  );
}
