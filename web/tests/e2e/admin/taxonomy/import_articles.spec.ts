import { expect, test, type Page } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

type TaxonomyDashboardFixture = {
  taxonomy: Record<string, unknown> | null;
  coverage: {
    total_documents: number;
    labeled_documents: number;
    coverage_percent: number;
  };
  summaries: Array<Record<string, unknown>>;
  recent_tasks: Array<Record<string, unknown>>;
};

const NOW = "2026-06-06T10:00:00.000Z";
const IMPORTED_FILE_NAME = "文章管理上传测试.md";
const IMPORTED_DOCUMENT_ID = "taxonomy_article__e2e-upload-test";

function jsonResponse(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  };
}

function activeTaxonomyDashboard(): TaxonomyDashboardFixture {
  return {
    taxonomy: {
      id: 1,
      name: "E2E 标签体系",
      active_version_id: 11,
      industry_context: null,
      company_description: "制造业知识治理测试",
      created_at: NOW,
      updated_at: NOW,
      active_version: {
        id: 11,
        taxonomy_id: 1,
        version_number: 1,
        status: "active",
        source: "manual",
        change_summary: "E2E active taxonomy",
        change_reason: null,
        effective_at: NOW,
        health_summary: null,
        created_at: NOW,
        updated_at: NOW,
        nodes: [],
      },
    },
    coverage: {
      total_documents: 0,
      labeled_documents: 0,
      coverage_percent: 0,
    },
    summaries: [],
    recent_tasks: [],
  };
}

function inactiveTaxonomyDashboard(): TaxonomyDashboardFixture {
  return {
    taxonomy: null,
    coverage: {
      total_documents: 0,
      labeled_documents: 0,
      coverage_percent: 0,
    },
    summaries: [],
    recent_tasks: [],
  };
}

function dashboardWithImportedArticle(): TaxonomyDashboardFixture {
  return {
    ...activeTaxonomyDashboard(),
    coverage: {
      total_documents: 1,
      labeled_documents: 0,
      coverage_percent: 0,
    },
    summaries: [
      {
        document_id: IMPORTED_DOCUMENT_ID,
        semantic_id: IMPORTED_FILE_NAME,
        summary: null,
        status: "pending",
        is_manual: false,
        failure_reason: null,
        generated_at: null,
        updated_at: NOW,
        current_label_status: null,
      },
    ],
    recent_tasks: [
      {
        id: 77,
        version_id: 11,
        status: "running",
        source: "summary",
        enable_optimization: false,
        optimization_strength: null,
        total_docs: 1,
        processed_docs: 0,
        failed_docs: 0,
        error_message: null,
        created_at: NOW,
        started_at: NOW,
        completed_at: null,
        updated_at: NOW,
      },
    ],
  };
}

async function mockCommonTaxonomyRoutes(page: Page) {
  await page.route("**/api/admin/taxonomy/documents/**/tags", async (route) => {
    await route.fulfill(jsonResponse([]));
  });
}

async function openImportsPage(page: Page) {
  await page.goto("/admin/taxonomy/imports");
  await expect(page.locator('[aria-label="admin-page-title"]')).toContainText(
    "文章管理"
  );
}

async function chooseArticleFile(
  page: Page,
  args: { name: string; body: string }
) {
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "选择文件", exact: true }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles({
    name: args.name,
    mimeType: args.name.endsWith(".md")
      ? "text/markdown"
      : "application/octet-stream",
    buffer: Buffer.from(args.body, "utf-8"),
  });
}

test.describe("Taxonomy article import upload", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");
    await mockCommonTaxonomyRoutes(page);
  });

  test("blocks article import until a taxonomy version is active", async ({
    page,
  }) => {
    await page.route("**/api/admin/taxonomy/dashboard", async (route) => {
      await route.fulfill(jsonResponse(inactiveTaxonomyDashboard()));
    });

    await openImportsPage(page);
    await expect(
      page.getByText("需先启用标签体系", { exact: true })
    ).toBeVisible();

    await page.getByRole("button", { name: "导入文章", exact: true }).click();
    await expect(
      page.getByText("请先创建并生效标签体系，再导入文章", { exact: true })
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("uploads a Markdown article and refreshes the processing list", async ({
    page,
  }) => {
    let importCompleted = false;
    let dashboardRequestsAfterImport = 0;
    const uploadRequests: Array<{ body: string; contentType: string }> = [];

    await page.route("**/api/admin/taxonomy/dashboard", async (route) => {
      if (!importCompleted) {
        await route.fulfill(jsonResponse(activeTaxonomyDashboard()));
        return;
      }

      dashboardRequestsAfterImport += 1;
      await route.fulfill(
        jsonResponse(
          dashboardRequestsAfterImport === 1
            ? activeTaxonomyDashboard()
            : dashboardWithImportedArticle()
        )
      );
    });

    await page.route("**/api/admin/taxonomy/articles/import", async (route) => {
      const request = route.request();
      uploadRequests.push({
        body: request.postData() ?? "",
        contentType: request.headers()["content-type"] ?? "",
      });
      importCompleted = true;
      await route.fulfill(
        jsonResponse({
          imported: [
            {
              file_name: IMPORTED_FILE_NAME,
              status: "queued",
              detail: "已上传，后台处理中",
            },
          ],
          failed: [],
        })
      );
    });

    await openImportsPage(page);
    await expect(page.getByText("暂无导入文章", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "导入文章", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("上传 Markdown 或 PDF 文件");
    await expect(dialog.getByText("未选择文件", { exact: true })).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "上传并处理", exact: true })
    ).toBeDisabled();

    await chooseArticleFile(page, {
      name: IMPORTED_FILE_NAME,
      body: "# 文章管理上传测试\n\n这是一篇用于验证导入链路的 Markdown 文章。",
    });
    await expect(
      dialog.getByText("1 个文件已选择", { exact: true })
    ).toBeVisible();
    await expect(
      dialog.getByText(IMPORTED_FILE_NAME, { exact: true })
    ).toBeVisible();

    await dialog
      .getByRole("button", { name: "上传并处理", exact: true })
      .click();

    await expect(
      page.getByText("已上传 1 个文件", { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText("后台正在接收文章", { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText("上传完成后会在这里显示处理进度")
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toBeHidden();

    expect(uploadRequests).toHaveLength(1);
    expect(uploadRequests[0]!.contentType).toContain("multipart/form-data");
    expect(uploadRequests[0]!.body).toContain('name="files"');
    expect(uploadRequests[0]!.body).toContain(
      `filename="${IMPORTED_FILE_NAME}"`
    );
    expect(uploadRequests[0]!.body).toContain(
      "这是一篇用于验证导入链路的 Markdown 文章"
    );

    await expect(
      page.getByText(IMPORTED_FILE_NAME, { exact: true })
    ).toBeVisible();
    await expect(page.getByText("入库文章", { exact: true })).toBeVisible();
    await expect(page.getByText("1 篇", { exact: true })).toBeVisible();
    await expect(
      page.getByText("文章列表 / 详情区", { exact: true })
    ).toBeVisible();
    await expect(page.getByText("正在总结", { exact: true })).toBeVisible();
    await expect(page.getByText("35%", { exact: true })).toBeVisible();
  });

  test("deletes an imported article from the processing list", async ({
    page,
  }) => {
    let deleted = false;
    const deletedArticleIds: string[] = [];

    await page.route("**/api/admin/taxonomy/dashboard", async (route) => {
      await route.fulfill(
        jsonResponse(
          deleted ? activeTaxonomyDashboard() : dashboardWithImportedArticle()
        )
      );
    });
    await page.route("**/api/admin/taxonomy/articles/**", async (route) => {
      if (route.request().method() !== "DELETE") {
        await route.fallback();
        return;
      }

      deleted = true;
      deletedArticleIds.push(route.request().url().split("/").pop() ?? "");
      await route.fulfill(
        jsonResponse({ status: "ok", deleted: IMPORTED_DOCUMENT_ID })
      );
    });

    await openImportsPage(page);
    await expect(
      page.getByText(IMPORTED_FILE_NAME, { exact: true })
    ).toBeVisible();

    await page.getByRole("button", { name: "删除文章", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("删除后会从文章导入列表");
    await expect(dialog).toContainText(IMPORTED_FILE_NAME);

    await dialog.getByRole("button", { name: "删除", exact: true }).click();

    await expect(page.getByText("文章已删除", { exact: true })).toBeVisible();
    await expect(page.getByText("暂无导入文章", { exact: true })).toBeVisible();
    await expect(
      page.getByText(IMPORTED_FILE_NAME, { exact: true })
    ).toBeHidden();
    expect(deletedArticleIds).toEqual([
      encodeURIComponent(IMPORTED_DOCUMENT_ID),
    ]);
  });

  test("surfaces unsupported article file upload errors", async ({ page }) => {
    await page.route("**/api/admin/taxonomy/dashboard", async (route) => {
      await route.fulfill(jsonResponse(activeTaxonomyDashboard()));
    });

    await page.route("**/api/admin/taxonomy/articles/import", async (route) => {
      await route.fulfill(
        jsonResponse({ detail: "仅支持 Markdown 和 PDF 文件" }, 400)
      );
    });

    await openImportsPage(page);
    await page.getByRole("button", { name: "导入文章", exact: true }).click();
    const dialog = page.getByRole("dialog");

    await chooseArticleFile(page, {
      name: "unsupported.docx",
      body: "not a supported article import format",
    });
    await expect(
      dialog.getByText("unsupported.docx", { exact: true })
    ).toBeVisible();

    await dialog
      .getByRole("button", { name: "上传并处理", exact: true })
      .click();

    await expect(
      page.getByText("仅支持 Markdown 和 PDF 文件", { exact: true })
    ).toBeVisible();
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "上传并处理", exact: true })
    ).toBeEnabled();
  });
});
