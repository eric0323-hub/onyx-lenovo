import { expect, type Locator, type Page } from "@playwright/test";

export class TaxonomyBuilderPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto() {
    await this.page.goto("/admin/taxonomy/template-draft");
    await expect(
      this.page.locator('[aria-label="admin-page-title"]')
    ).toContainText("标签体系");
  }

  get promptInput(): Locator {
    return this.page.getByPlaceholder("例如：我们是一家制造业企业", {
      exact: false,
    });
  }

  get generateButton(): Locator {
    return this.page.getByRole("button", { name: "生成", exact: true });
  }

  get saveDraftButton(): Locator {
    return this.page.getByRole("button", { name: "保存草稿", exact: true });
  }

  get applyJsonButton(): Locator {
    return this.page.getByRole("button", { name: "应用编辑", exact: true });
  }

  get treeTab(): Locator {
    return this.page.getByRole("button", { name: "树", exact: true });
  }

  get jsonTab(): Locator {
    return this.page.getByRole("button", { name: "JSON", exact: true });
  }

  get modificationNoteInput(): Locator {
    return this.page.getByPlaceholder("例如：新增设备维修相关标签", {
      exact: false,
    });
  }

  get jsonEditor(): Locator {
    return this.page.getByTestId("taxonomy-json-editor");
  }

  async generateWithPrompt(prompt: string) {
    await this.promptInput.fill(prompt);
    await this.generateButton.click();
    await expect(
      this.page.getByText("标签体系已生成，可以继续编辑完善", { exact: true })
    ).toBeVisible();
  }

  async expectNodeVisible(name: string) {
    await expect(this.page.getByText(name, { exact: true })).toBeVisible();
  }

  async expectNodeHidden(name: string) {
    await expect(this.page.getByText(name, { exact: true })).toBeHidden();
  }

  async openJsonEditor() {
    await this.jsonTab.click();
    await expect(this.jsonEditor).toBeVisible();
  }

  async openTreeEditor() {
    await this.treeTab.click();
    await expect(this.page.locator(".taxonomy-tree")).toBeVisible();
  }

  async expectJsonContains(value: string) {
    await expect(this.jsonEditor).toHaveValue(new RegExp(value));
  }

  async fillJson(value: string) {
    await this.jsonEditor.fill(value);
  }

  async applyJson() {
    await this.applyJsonButton.click();
    await expect(this.page.getByText("已应用 JSON 编辑内容")).toBeVisible();
  }

  async openAddRootModal() {
    await this.page.getByRole("button", { name: "新增一级" }).click();
    await expect(this.page.getByRole("dialog")).toContainText("新增一级标签");
  }

  async addNode(name: string, definition: string) {
    const dialog = this.page.getByRole("dialog");
    await dialog.locator("input").fill(name);
    await dialog.locator("textarea").fill(definition);
    await dialog.getByRole("button", { name: "确定", exact: true }).click();
    await expect(dialog).toBeHidden();
  }

  async deleteNode(name: string) {
    const node = this.page.getByTestId(`taxonomy-node-${name}`);
    await node.hover();
    await node.getByRole("button", { name: "删除标签" }).click();
    const dialog = this.page.getByRole("dialog");
    await expect(dialog).toContainText(`确定删除「${name}`);
    await dialog.getByRole("button", { name: "删除", exact: true }).click();
    await expect(dialog).toBeHidden();
  }

  async editNodeName(currentName: string, nextName: string) {
    await this.page.getByLabel(`编辑标签 ${currentName}`).click();
    const dialog = this.page.getByRole("dialog");
    await expect(dialog).toContainText("编辑标签");
    await dialog.locator("input").fill(nextName);
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
  }

  async saveDraft(note?: string) {
    if (note !== undefined) {
      await this.modificationNoteInput.fill(note);
    }
    await this.saveDraftButton.click();
    await expect(this.page.getByText(/^草稿 v\d+ 已保存$/)).toBeVisible();
  }
}

export class TaxonomyHistoryPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto() {
    await this.page.goto("/admin/taxonomy/history");
    await expect(
      this.page.locator('[aria-label="admin-page-title"]')
    ).toContainText("版本记录");
  }

  async expectVersionNote(note: string) {
    await expect(this.page.getByText(note, { exact: false })).toBeVisible();
  }
}
