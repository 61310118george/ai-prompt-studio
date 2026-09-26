# 下一步行動

## 目前階段

2026-09-25：已補上一般提示詞管理、引導模板、版本、Token 計數與成本情境。下一步以老師確認研究問題、真實語料、使用者试測及模型品質比較為主。完整步驟見 [研究與展示指南](研究與展示指南.md)。下列 2.0 清單保留為沿革，不取代 [最新 spec](SPEC.md) 與 [符合度稽核](現況符合度與交付紀錄.md)。

## 已完成

- [x] pywebview 共用 Web UI 架構
- [x] 瀏覽器 MockApi 與桌面 DesktopApi
- [x] 四大區導航：專案、記憶編程、記憶健檢、設定
- [x] Codex、Claude Code、Gemini CLI、OpenClaw 規格目錄
- [x] 15 種結構化記憶模組
- [x] 離線 Markdown compiler
- [x] managed section 合併與 unified diff
- [x] SHA-256 外部修改保護
- [x] atomic write、Application Support 備份與復原
- [x] 路徑穿越與 symlink 越界防護
- [x] 記憶健檢與有效記憶模擬
- [x] SQLite 2.0 additive migration
- [x] 保留舊 PySide6 啟動入口
- [x] 桌面及 375px 響應式 Web 驗證
- [x] 自動化核心測試
- [x] 產生 `AI Memory Manager Next.app`
- [x] 實際啟動打包 App，確認 pywebview bridge、規格資源與四大導航載入

## 下一步人工驗收

- [ ] 雙擊開啟 `dist/AI Memory Manager Next.app`
- [ ] 選擇一個非重要的測試根目錄
- [ ] 測試四種 Agent 與不同記憶模組
- [ ] 確認 Diff、套用、外部修改拒絕與復原
- [ ] 檢查長檔名、空專案、深層資料夾與大量 Markdown 的操作感受
- [ ] 根據真實使用回饋微調表單文案與模板
- [ ] 決定是否以 Next 版正式取代 1.x App
- [ ] 若要對外發布，再評估 Developer ID、notarization 與正式版本號
