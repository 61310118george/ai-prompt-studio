# `.codex/config.toml` 範本

目前 Codex 無法在此工作區建立 `.codex/` 目錄，因此先將設定範本記錄於本檔案。

當 `.codex/` 可寫入後，建議建立：

```text
.codex/config.toml
```

初始內容建議保持保守，不加入尚未確認的模型、MCP 或 hook 設定：

```toml
# Codex project configuration
# 本檔只放 Codex 專案層級設定，不放畢專需求內容。

# 待後續依需求加入：
# - MCP servers
# - hooks
# - model or reasoning defaults
# - sandbox-related settings
```

