import { expect, test, type Page, type Route } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  TaxonomyBuilderPage,
  TaxonomyHistoryPage,
} from "./TaxonomyBuilderPage";

type TaxonomyNodeFixture = {
  id?: string | null;
  parent_id?: string | null;
  level: "l1" | "l2" | "leaf";
  name: string;
  definition: string;
  applicability: string;
  exclusion?: string | null;
  positive_examples: string[];
  negative_examples: string[];
  keywords: string[];
  synonyms: string[];
  source: "ai_generated" | "manual";
  status: "draft" | "active";
  sort_order: number;
  children: TaxonomyNodeFixture[];
};

type TaxonomyVersionFixture = {
  id: number;
  taxonomy_id: number;
  version_number: number;
  status: "draft" | "active" | "superseded" | "deprecated";
  source: "manual" | "ai_generated";
  change_summary: string;
  change_reason: string | null;
  effective_at: string | null;
  health_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  nodes: TaxonomyNodeFixture[];
};

const TAXONOMY_PROMPT =
  "我们是一家制造业企业，知识库包含设备运维、质量复盘、制度流程和安全生产文档。请生成三级标签体系。";
const TAXONOMY_GENERATION_STORAGE_KEY =
  "onyx.taxonomy.templateDraft.generation.v1";

function nodeFixture(
  level: TaxonomyNodeFixture["level"],
  name: string,
  definition: string,
  children: TaxonomyNodeFixture[] = []
): TaxonomyNodeFixture {
  return {
    id: `${level}-${name}`,
    parent_id: null,
    level,
    name,
    definition,
    applicability: definition,
    exclusion: null,
    positive_examples: level === "leaf" ? [`${name} 正例`] : [],
    negative_examples: level === "leaf" ? [`${name} 反例`] : [],
    keywords: [name],
    synonyms: [],
    source: "ai_generated",
    status: "draft",
    sort_order: 0,
    children,
  };
}

function generatedTaxonomyTree(): TaxonomyNodeFixture[] {
  return [
    nodeFixture("l1", "设备运维", "设备维护、巡检和故障处理相关知识", [
      nodeFixture("l2", "维修知识", "维修手册、故障排查和备件说明", [
        nodeFixture("leaf", "故障排查", "定位设备异常原因并给出处置步骤"),
      ]),
    ]),
    nodeFixture("l1", "质量管理", "质量标准、问题复盘和改善闭环", [
      nodeFixture("l2", "质量复盘", "质量异常的分析和经验沉淀", [
        nodeFixture("leaf", "问题复盘", "记录质量问题原因、影响和纠正措施"),
      ]),
    ]),
  ];
}

function regeneratedTaxonomyTree(): TaxonomyNodeFixture[] {
  return [
    nodeFixture("l1", "售后知识", "客户咨询、故障受理和解决方案相关知识", [
      nodeFixture("l2", "客户咨询", "客服问答、操作指导和问题分流", [
        nodeFixture("leaf", "操作指导", "面向客户的产品操作步骤和注意事项"),
      ]),
    ]),
  ];
}

function jsonResponse(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  };
}

function streamResponse(events: unknown[], status = 200) {
  return {
    status,
    contentType: "text/event-stream",
    body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
  };
}

function taxonomyGenerationEvents(nodes: TaxonomyNodeFixture[]) {
  return [
    {
      type: "stage",
      message: "正在生成一级标签",
      progress: 5,
    },
    {
      type: "nodes",
      message: "一级标签已生成，开始并行生成二级标签",
      nodes,
      progress: 12,
    },
    {
      type: "final",
      message: "标签体系已完成最终优化",
      nodes,
      progress: 100,
    },
  ];
}

async function mockTaxonomyApis(page: Page) {
  let nextVersionId = 10;
  const versions: TaxonomyVersionFixture[] = [];
  const draftRequests: unknown[] = [];
  const generateRequests: unknown[] = [];

  await page.route("**/api/admin/taxonomy/dashboard", async (route) => {
    await route.fulfill(
      jsonResponse({
        taxonomy: null,
        coverage: {
          total_documents: 0,
          labeled_documents: 0,
          coverage_percent: 0,
        },
        summaries: [],
        recent_tasks: [],
      })
    );
  });

  await page.route("**/api/admin/taxonomy/versions", async (route) => {
    await route.fulfill(jsonResponse(versions));
  });

  await page.route("**/api/admin/taxonomy/generate-draft", async (route) => {
    generateRequests.push(route.request().postDataJSON());
    await route.fulfill(jsonResponse({ nodes: generatedTaxonomyTree() }));
  });

  await page.route(
    "**/api/admin/taxonomy/generate-draft/stream",
    async (route) => {
      generateRequests.push(route.request().postDataJSON());
      await route.fulfill(
        streamResponse(taxonomyGenerationEvents(generatedTaxonomyTree()))
      );
    }
  );

  await page.route("**/api/admin/taxonomy/draft", async (route: Route) => {
    const body = route.request().postDataJSON() as {
      generated_nodes: TaxonomyNodeFixture[];
      change_reason: string;
    };
    draftRequests.push(body);

    const now = new Date().toISOString();
    const version: TaxonomyVersionFixture = {
      id: nextVersionId++,
      taxonomy_id: 1,
      version_number: versions.length + 1,
      status: "draft",
      source: "manual",
      change_summary: "Created taxonomy draft",
      change_reason: body.change_reason,
      effective_at: null,
      health_summary: null,
      created_at: now,
      updated_at: now,
      nodes: body.generated_nodes,
    };
    versions.unshift(version);
    await route.fulfill(jsonResponse(version));
  });

  return {
    versions,
    draftRequests,
    generateRequests,
  };
}

test.describe("Taxonomy builder", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");
  });

  test("generates a taxonomy from prompt and keeps tree and JSON in sync", async ({
    page,
  }) => {
    const api = await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);

    await builder.goto();
    await builder.generateButton.click();
    await expect(
      page.getByText("请先输入标签体系建设提示词", { exact: true })
    ).toBeVisible();

    await builder.generateWithPrompt(TAXONOMY_PROMPT);

    expect(api.generateRequests).toHaveLength(1);
    expect(api.generateRequests[0]).toMatchObject({
      company_description: TAXONOMY_PROMPT,
    });
    expect(api.generateRequests[0]).not.toHaveProperty("industry_context");

    await builder.expectNodeVisible("设备运维");
    await builder.expectNodeVisible("故障排查");
    await expect(page.getByText("一级 2 · 二级 2 · 三级 2")).toBeVisible();

    await builder.openJsonEditor();
    await builder.expectJsonContains("设备运维");
    await builder.expectJsonContains("故障排查");
  });

  test("clears the previous tree while the next taxonomy is still generating", async ({
    page,
  }) => {
    await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);

    await builder.goto();
    await builder.generateWithPrompt(TAXONOMY_PROMPT);
    await builder.expectNodeVisible("设备运维");

    await page.unroute("**/api/admin/taxonomy/generate-draft/stream");

    let resolveStreamRequested: () => void = () => undefined;
    const streamRequested = new Promise<void>((resolve) => {
      resolveStreamRequested = resolve;
    });
    let releaseStream: () => void = () => undefined;
    const streamReleased = new Promise<void>((resolve) => {
      releaseStream = resolve;
    });

    await page.route(
      "**/api/admin/taxonomy/generate-draft/stream",
      async (route) => {
        resolveStreamRequested();
        await streamReleased;
        await route.fulfill(
          streamResponse(taxonomyGenerationEvents(regeneratedTaxonomyTree()))
        );
      }
    );

    await builder.promptInput.fill(`${TAXONOMY_PROMPT} 第二版`);
    await builder.generateButton.click();
    await streamRequested;

    await expect(
      page.locator("#taxonomy-builder").getByText("正在生成中", {
        exact: true,
      })
    ).toBeVisible();
    await builder.expectNodeHidden("设备运维");
    await expect(page.getByText("一级 0 · 二级 0 · 三级 0")).toBeVisible();

    releaseStream();

    await builder.expectNodeVisible("售后知识");
  });

  test("restores the in-progress taxonomy generation after refresh", async ({
    page,
  }) => {
    await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);
    await builder.goto();

    await page.unroute("**/api/admin/taxonomy/generate-draft/stream");
    let resolveStreamRequested: () => void = () => undefined;
    const streamRequested = new Promise<void>((resolve) => {
      resolveStreamRequested = resolve;
    });
    let releaseStream: () => void = () => undefined;
    const streamReleased = new Promise<void>((resolve) => {
      releaseStream = resolve;
    });

    await page.route(
      "**/api/admin/taxonomy/generate-draft/stream",
      async (route) => {
        resolveStreamRequested();
        await streamReleased;
        await route.fulfill(
          streamResponse(taxonomyGenerationEvents(regeneratedTaxonomyTree()))
        );
      }
    );

    await page.evaluate(
      ({ prompt, nodes, storageKey }) => {
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            prompt,
            status: {
              message: "一级标签已生成，开始并行生成二级标签",
              progress: 12,
            },
            nodes,
          })
        );
      },
      {
        prompt: TAXONOMY_PROMPT,
        nodes: generatedTaxonomyTree(),
        storageKey: TAXONOMY_GENERATION_STORAGE_KEY,
      }
    );

    const reloadPromise = page.reload();
    await streamRequested;

    await expect(builder.promptInput).toHaveValue(TAXONOMY_PROMPT);
    await expect(
      page
        .locator("#taxonomy-builder")
        .getByText("一级标签已生成，开始并行生成二级标签", {
          exact: true,
        })
    ).toBeVisible();
    await builder.expectNodeVisible("设备运维");

    releaseStream();
    await reloadPromise;

    await builder.expectNodeVisible("售后知识");
    await expect(builder.promptInput).toHaveValue("");
  });

  test("adds and deletes labels on the tree and mirrors those changes to JSON", async ({
    page,
  }) => {
    await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);

    await builder.goto();
    await builder.generateWithPrompt(TAXONOMY_PROMPT);

    await builder.openAddRootModal();
    await builder.addNode("安全生产", "安全制度、风险控制和事故预防相关知识");
    await builder.expectNodeVisible("安全生产");
    await expect(page.getByText("一级 3 · 二级 2 · 三级 2")).toBeVisible();

    await builder.deleteNode("安全生产");
    await builder.expectNodeHidden("安全生产");
    await expect(page.getByText("一级 2 · 二级 2 · 三级 2")).toBeVisible();

    await builder.openJsonEditor();
    await expect(builder.jsonEditor).not.toHaveValue(/安全生产/);
  });

  test("tree edits update JSON and JSON edits update the tree", async ({
    page,
  }) => {
    await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);

    await builder.goto();
    await builder.generateWithPrompt(TAXONOMY_PROMPT);

    await builder.editNodeName("设备运维", "设备维护");
    await builder.expectNodeVisible("设备维护");

    await builder.openJsonEditor();
    await builder.expectJsonContains("设备维护");

    const updatedTree = generatedTaxonomyTree();
    const firstNode = updatedTree[0]!;
    updatedTree[0] = {
      ...firstNode,
      name: "知识制度",
      definition: "制度流程、岗位规范和合规要求",
      applicability: "制度流程、岗位规范和合规要求",
      children: [],
    };

    await builder.fillJson(JSON.stringify(updatedTree, null, 2));
    await builder.applyJson();
    await builder.expectNodeVisible("知识制度");
    await builder.expectNodeHidden("设备维护");

    await builder.openJsonEditor();
    await builder.fillJson('{"bad": true}');
    await builder.applyJsonButton.click();
    await expect(
      page
        .locator("#taxonomy-builder")
        .getByText("JSON 内容必须是 Taxonomy 节点数组")
    ).toBeVisible();
  });

  test("saves drafts with optional modification notes and shows them in history", async ({
    page,
  }) => {
    const api = await mockTaxonomyApis(page);
    const builder = new TaxonomyBuilderPage(page);

    await builder.goto();
    await builder.generateWithPrompt(TAXONOMY_PROMPT);
    await builder.saveDraft("补充制造业设备和质量场景标签");

    expect(api.draftRequests).toHaveLength(1);
    expect(api.draftRequests[0]).toMatchObject({
      company_description: TAXONOMY_PROMPT,
      change_reason: "补充制造业设备和质量场景标签",
    });

    await expect(
      page.locator("#taxonomy-builder").getByText("草稿 v1", { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText("补充制造业设备和质量场景标签", { exact: true })
    ).toBeVisible();

    await page.reload();
    await builder.generateWithPrompt(TAXONOMY_PROMPT);
    await builder.saveDraft();
    expect(api.draftRequests[1]).toMatchObject({
      change_reason: "手动保存标签体系草稿",
    });

    const history = new TaxonomyHistoryPage(page);
    await history.goto();
    await history.expectVersionNote("补充制造业设备和质量场景标签");
    await history.expectVersionNote("手动保存标签体系草稿");
  });
});
