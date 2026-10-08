"""Build portable, printable HTML from the authoritative Markdown documents."""
from pathlib import Path
import html
import markdown

root = Path(__file__).resolve().parents[1]
output = root / "deliverables"
output.mkdir(exist_ok=True)
documents = [("專題企劃書.md", "專題企劃書.html"), ("SPEC.md", "軟體規格書.html"),
             ("現況符合度與交付紀錄.md", "現況符合度.html"), ("研究與展示指南.md", "研究與展示指南.html")]
style = """
body{margin:0;background:#f1eee8;color:#222;font-family:-apple-system,BlinkMacSystemFont,'PingFang TC','Noto Sans TC',sans-serif;line-height:1.8}
main{max-width:900px;margin:36px auto;background:white;padding:52px 64px;box-shadow:0 12px 50px #0001}
h1,h2,h3{color:#111;line-height:1.4;break-after:avoid}h1{font-size:29px;border-bottom:2px solid #333;padding-bottom:20px}h2{font-size:23px;margin-top:40px}h3{font-size:18px;margin-top:26px}
p,li{font-size:15px}table{border-collapse:collapse;width:100%;font-size:13px;margin:18px 0 24px}th,td{border:1px solid #d9d9d9;padding:10px 12px;text-align:left;vertical-align:top}th{background:#edf1f5}tr{break-inside:avoid}thead{display:table-header-group}
a{color:#275678;overflow-wrap:anywhere}code{font-size:.88em;background:#f5f5f5;padding:2px 4px;overflow-wrap:anywhere}pre{white-space:pre-wrap}img{display:block;max-width:100%;height:auto;margin:18px auto;border:1px solid #ddd}nav{font-size:14px;padding-bottom:16px;border-bottom:1px solid #ddd}
@media(max-width:760px){main{margin:0;padding:25px 20px}table{font-size:12px}th,td{padding:6px}}
@media print{@page{size:A4;margin:18mm}body{background:white}main{max-width:none;margin:0;padding:0;box-shadow:none}nav{display:none}h1{font-size:24px}h2{font-size:19px}p,li{font-size:11pt}table{font-size:9.5pt}a{color:#111;text-decoration:none}}
"""
for source, target in documents:
    source_text = (root / "docs" / source).read_text(encoding="utf-8")
    source_text = source_text.replace("](evidence/", "](../docs/evidence/")
    content = markdown.markdown(source_text, extensions=["tables", "fenced_code", "toc"])
    navigation = ' · '.join(f'<a href="{html.escape(name)}">{html.escape(name.removesuffix(".html"))}</a>' for _, name in documents)
    page = f'<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(source)}</title><style>{style}</style><main><nav>{navigation} · 可使用瀏覽器列印</nav>{content}</main></html>'
    (output / target).write_text(page, encoding="utf-8")
    print(output / target)
