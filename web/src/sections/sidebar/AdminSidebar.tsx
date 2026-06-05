"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useSettingsContext } from "@/providers/SettingsProvider";
import SidebarSection from "@/sections/sidebar/SidebarSection";
import * as SidebarLayouts from "@/layouts/sidebar-layouts";
import { useSidebarFolded } from "@/layouts/sidebar-layouts";
import { useUser } from "@/providers/UserProvider";
import { UserRole } from "@/lib/types";
import { CombinedSettings } from "@/interfaces/settings";
import { Divider, SidebarTab } from "@opal/components";
import InputTypeIn from "@/refresh-components/inputs/InputTypeIn";
import Spacer from "@/refresh-components/Spacer";
import { SvgSearch, SvgX } from "@opal/icons";
import { ADMIN_ROUTES, sidebarItem } from "@/lib/admin-routes";
import useFilter from "@/hooks/useFilter";
import { IconFunctionComponent } from "@opal/types";
import AccountPopover from "@/sections/sidebar/AccountPopover";
import { useSidebarState } from "@/layouts/sidebar-layouts";
import { isAdminRouteVisible } from "@/lib/featureVisibility";

const SECTIONS = {
  UNLABELED: "",
  AGENTS_AND_ACTIONS: "Agents & Actions",
  DOCUMENTS_AND_KNOWLEDGE: "Documents & Knowledge",
  LABEL_AND_TAXONOMY: "标签治理",
  INTEGRATIONS: "Integrations",
  PERMISSIONS: "Permissions",
  ORGANIZATION: "Organization",
  USAGE: "Usage",
} as const;

interface SidebarItemEntry {
  section: string;
  name: string;
  icon: IconFunctionComponent;
  link: string;
  error?: boolean;
}

function buildItems(
  isCurator: boolean,
  settings: CombinedSettings | null
): SidebarItemEntry[] {
  const vectorDbEnabled = settings?.settings.vector_db_enabled !== false;
  const items: SidebarItemEntry[] = [];

  const add = (section: string, route: Parameters<typeof sidebarItem>[0]) => {
    if (!isAdminRouteVisible(route)) {
      return;
    }
    items.push({ ...sidebarItem(route), section });
  };

  // 1. No header — core configuration (admin only)
  if (!isCurator) {
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.LLM_MODELS);
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.WEB_SEARCH);
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.IMAGE_GENERATION);
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.VOICE);
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.CODE_INTERPRETER);
    add(SECTIONS.UNLABELED, ADMIN_ROUTES.CHAT_PREFERENCES);
  }

  // 2. Agents & Actions
  add(SECTIONS.AGENTS_AND_ACTIONS, ADMIN_ROUTES.AGENTS);
  add(SECTIONS.AGENTS_AND_ACTIONS, ADMIN_ROUTES.SKILLS);
  add(SECTIONS.AGENTS_AND_ACTIONS, ADMIN_ROUTES.MCP_ACTIONS);
  add(SECTIONS.AGENTS_AND_ACTIONS, ADMIN_ROUTES.OPENAPI_ACTIONS);

  // 3. Documents & Knowledge
  if (vectorDbEnabled) {
    add(SECTIONS.DOCUMENTS_AND_KNOWLEDGE, ADMIN_ROUTES.INDEXING_STATUS);
    add(SECTIONS.DOCUMENTS_AND_KNOWLEDGE, ADMIN_ROUTES.ADD_CONNECTOR);
    add(SECTIONS.DOCUMENTS_AND_KNOWLEDGE, ADMIN_ROUTES.DOCUMENT_SETS);
    if (!isCurator) {
      if (isAdminRouteVisible(ADMIN_ROUTES.INDEX_SETTINGS)) {
        items.push({
          ...sidebarItem(ADMIN_ROUTES.INDEX_SETTINGS),
          section: SECTIONS.DOCUMENTS_AND_KNOWLEDGE,
          error: settings?.settings.needs_reindexing,
        });
      }
    }
  }

  // 4. Label & Taxonomy
  add(SECTIONS.LABEL_AND_TAXONOMY, ADMIN_ROUTES.TAXONOMY);
  add(SECTIONS.LABEL_AND_TAXONOMY, ADMIN_ROUTES.TAXONOMY_IMPORTS);

  // 5. Integrations (admin only)
  if (!isCurator) {
    add(SECTIONS.INTEGRATIONS, ADMIN_ROUTES.API_KEYS);
    add(SECTIONS.INTEGRATIONS, ADMIN_ROUTES.SLACK_BOTS);
    add(SECTIONS.INTEGRATIONS, ADMIN_ROUTES.DISCORD_BOTS);
  }

  // 6. Permissions
  if (!isCurator) {
    add(SECTIONS.PERMISSIONS, ADMIN_ROUTES.USERS);
    add(SECTIONS.PERMISSIONS, ADMIN_ROUTES.GROUPS);
  }

  // 7. Organization (admin only)
  if (!isCurator) {
    add(SECTIONS.ORGANIZATION, ADMIN_ROUTES.TOKEN_RATE_LIMITS);
  }

  // 8. Usage and observability (admin only)
  if (!isCurator) {
    add(SECTIONS.USAGE, ADMIN_ROUTES.OBSERVABILITY);
  }

  return items;
}

/** Preserve section ordering while grouping consecutive items by section. */
function groupBySection(items: SidebarItemEntry[]) {
  const groups: { section: string; items: SidebarItemEntry[] }[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.section === item.section) {
      last.items.push(item);
    } else {
      groups.push({ section: item.section, items: [item] });
    }
  }
  return groups;
}

function isPathSelected(pathname: string, link: string): boolean {
  return pathname === link || pathname.startsWith(`${link}/`);
}

function getSelectedSidebarLink(
  pathname: string,
  items: SidebarItemEntry[]
): string | undefined {
  if (
    pathname.startsWith("/admin/taxonomy/") &&
    !isPathSelected(pathname, ADMIN_ROUTES.TAXONOMY_IMPORTS.path)
  ) {
    return ADMIN_ROUTES.TAXONOMY.path;
  }

  return items
    .filter((item) => isPathSelected(pathname, item.link))
    .sort((a, b) => b.link.length - a.link.length)[0]?.link;
}

function AdminSidebarInner() {
  const { setFolded } = useSidebarState();
  const folded = useSidebarFolded();
  const searchRef = useRef<HTMLInputElement>(null);
  const [focusSearch, setFocusSearch] = useState(false);

  useEffect(() => {
    if (focusSearch && !folded && searchRef.current) {
      searchRef.current.focus();
      setFocusSearch(false);
    }
  }, [focusSearch, folded]);
  const pathname = usePathname();
  const { user } = useUser();
  const settings = useSettingsContext();
  const isCurator =
    user?.role === UserRole.CURATOR || user?.role === UserRole.GLOBAL_CURATOR;

  const allItems = buildItems(isCurator, settings);

  const itemExtractor = useCallback((item: SidebarItemEntry) => item.name, []);

  const { query, setQuery, filtered } = useFilter(allItems, itemExtractor);

  const enabledGroups = groupBySection(filtered);
  const selectedLink = getSelectedSidebarLink(pathname, allItems);

  return (
    <>
      <SidebarLayouts.Header>
        {folded ? (
          <SidebarTab
            icon={SvgSearch}
            folded
            onClick={() => {
              setFolded(false);
              setFocusSearch(true);
            }}
          >
            Search
          </SidebarTab>
        ) : (
          <InputTypeIn
            ref={searchRef}
            variant="internal"
            leftSearchIcon
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        )}
      </SidebarLayouts.Header>

      <SidebarLayouts.Body scrollKey="admin-sidebar">
        {enabledGroups.map((group, groupIndex) => {
          const tabs = group.items.map(({ link, icon, name }) => (
            <SidebarTab
              key={link}
              icon={icon}
              href={link}
              selected={selectedLink === link}
            >
              {name}
            </SidebarTab>
          ));

          if (!group.section) {
            return <div key={groupIndex}>{tabs}</div>;
          }

          return (
            <SidebarSection key={groupIndex} title={group.section}>
              {tabs}
            </SidebarSection>
          );
        })}
      </SidebarLayouts.Body>

      <SidebarLayouts.Footer>
        {!folded && (
          <>
            <Divider paddingPerpendicular="fit" />
            <Spacer rem={0.5} />
          </>
        )}
        <SidebarTab
          icon={SvgX}
          href="/app"
          variant="sidebar-light"
          folded={folded}
        >
          Exit Admin Panel
        </SidebarTab>
        <AccountPopover folded={folded} />
      </SidebarLayouts.Footer>
    </>
  );
}

export default function AdminSidebar() {
  return (
    <SidebarLayouts.Root>
      <AdminSidebarInner />
    </SidebarLayouts.Root>
  );
}
