# UI/UX 參考來源

## 參考 Repo

- 名稱：`nextlevelbuilder/ui-ux-pro-max-skill`
- GitHub：`https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`
- 授權：MIT License

## 初步理解

此 repo 是一個 AI UI/UX skill，主要提供：

- UI styles
- color palettes
- typography pairings
- UX guidelines
- chart recommendations
- design system generation
- 多平台或多技術棧的 UI/UX 指引

## 對本專題的用途

本專題可以將它作為：

- UI/UX 設計參考
- 設計系統生成參考
- 視覺風格選擇輔助
- 可用性與無障礙檢查清單
- 畢專報告中「設計方法」的參考依據之一

## 限制

- 它不是 Python 桌面 GUI 框架。
- 它不能直接取代 PySide6、PyQt 或 Tkinter。
- 它支援的桌面 stack 中有 JavaFX，但目前沒有明確以 Python 桌面 GUI 作為主要支援對象。
- 若要完整安裝或引用，需要後續確認是否要將其 CLI 或 skill 內容整合到本專案流程。

## 初步採用方式

- 使用者已要求安裝此 skill。
- 使用者已透過 `uipro init --ai codex` 安裝到目前專案。
- 安裝位置：`.codex/skills/ui-ux-pro-max/`
- Codex 已確認可讀取 `.codex/skills/ui-ux-pro-max/SKILL.md`。
- 後續當任務涉及 UI 結構、視覺設計、互動模式或 UX 品質控制時，應使用此 skill 作為設計依據。

## 建議手動安裝指令

已完成。使用者執行的安裝方式：

```bash
npm install -g ui-ux-pro-max-cli
uipro init --ai codex
```

若要使用 Codex 官方 skill installer 的 GitHub repo path 方式，目標 skill path 是：

```text
nextlevelbuilder/ui-ux-pro-max-skill/.claude/skills/ui-ux-pro-max
```

## 已安裝內容摘要

目前專案產生的主要 skill：

- `.codex/skills/ui-ux-pro-max/`
- `.codex/skills/design/`
- `.codex/skills/banner-design/`
- `.codex/skills/ui-styling/`
- `.codex/skills/brand/`
- `.codex/skills/slides/`
- `.codex/skills/design-system/`

`ui-ux-pro-max` 主 skill 提供：

- 67 種 UI styles
- 161 組 color palettes
- 57 組 font pairings
- 99 條 UX guidelines
- 25 種 chart types
- 22 種 technology stacks
- 可搜尋設計資料庫

## 使用規則

當本專題進入以下工作時使用：

- 設計 macOS 桌面 app 主要畫面
- 設計記憶區塊管理 UI
- 設計提示詞編輯器與版本差異畫面
- 設計 AI 精簡器操作流程
- 選擇配色、字體、間距與設計系統
- 檢查 UI 可讀性、可用性、視覺一致性與互動回饋
