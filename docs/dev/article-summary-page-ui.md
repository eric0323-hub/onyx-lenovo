# Article Summary Page UI Brief

Use this brief only when the task is specifically about the article summary/import page or when the user explicitly references this document.

## Layout Structure

1. **Page Header**: page title, description, and import action.
2. **Stats Bar**: four independent statistic cards in a horizontal row with consistent gaps.
3. **Article List / Detail Area**: clear card container for the main article workflow.
4. **Summary Editing Area**: independent card or framed editing surface.

## Layout Rules

- Use card-based layout with clear visual hierarchy.
- Use 8px or 12px spacing multiples such as 8, 16, 24, 32, and 48.
- Use Grid or Flex for strict alignment.
- The page should feel clean and operational, similar to Notion, Linear, Vercel, or Feishu document-management screens.
- This brief is desktop-only unless the user explicitly requests mobile support.

## Component Details

- Cards should use consistent padding, preferably 20px or 24px.
- Card radius should be consistent, preferably 12px or 16px when compatible with the surrounding design system.
- Statistic metrics must be independent statistic cards instead of visually crowded inline values.
- Article cards should use two or three desktop columns:
  - Left: article information and status.
  - Middle: summary editor as the primary workspace.
  - Right: progress and actions stacked vertically.
- Progress bars and status text must not overlap or sit too close together.
- Important actions such as saving a summary or importing articles should be visually prominent.
- Empty, loading, progress, and completed states should be visually distinct.

## Text

- Chinese paragraph-like text should use line-height 1.6 to 1.8.
- Avoid dense blocks of text in operational UI.
