# 正式共用 Web UI

## 定位

`web-preview/` 從 1.x 的靜態 UI 原型升級為 2.0 正式前端。

同一套 HTML、CSS、JavaScript 會運行在兩種模式：

- 瀏覽器模式：使用 `MockApi` 與示範專案，不碰真實檔案。
- 桌面模式：由 pywebview 載入，透過 `window.pywebview.api` 呼叫 Python、SQLite 與檔案服務。

這代表 UI 不需要再人工重寫成 PySide6。

## 開啟瀏覽器版本

從專案根目錄執行：

```bash
python3 -m http.server 4173 --directory .
```

打開：

```text
http://127.0.0.1:4173/web-preview/
```

## 四大區

1. 專案
2. 記憶編程
3. 記憶健檢
4. 設定

## 開發規則

- 所有真實檔案操作都放在 Python `DesktopApi`，不要直接在 JavaScript 模擬權限。
- 瀏覽器 Mock 與桌面 bridge 使用相同方法名稱及回應格式。
- 主要按鈕與欄位至少 44px 高。
- 使用可見 label、鍵盤 focus ring、ARIA 狀態與 `prefers-reduced-motion`。
- 前端不載入線上字型或 JavaScript 套件，確保離線可用。
