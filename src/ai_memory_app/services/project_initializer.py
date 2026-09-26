from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InitializerQuestion:
    key: str
    label: str
    placeholder: str


@dataclass(frozen=True)
class InitializerTemplate:
    key: str
    label: str
    description: str
    questions: tuple[InitializerQuestion, ...]


INITIALIZER_TEMPLATES = {
    "solo_ai": InitializerTemplate(
        key="solo_ai",
        label="單人 AI 協作",
        description="適合一個使用者與 AI 一起完成程式、報告、整理或研究任務。",
        questions=(
            InitializerQuestion("goal", "專案目標", "這個專案最後要完成什麼？"),
            InitializerQuestion("current_state", "目前狀態", "目前已經做到哪裡？有哪些既有檔案、資料或想法？"),
            InitializerQuestion("ai_role", "AI 負責內容", "希望 AI 主要協助規劃、寫程式、除錯、整理文件，或其他工作？"),
            InitializerQuestion("user_role", "我負責內容", "哪些事情必須由你決定、確認或提供資料？"),
            InitializerQuestion("constraints", "限制條件", "時間、預算、技術、學校要求、不能碰的方向。"),
            InitializerQuestion("working_rules", "工作規則", "希望 AI 如何回覆、何時先問、何時直接實作、語言與格式偏好。"),
            InitializerQuestion("next_steps", "下一步任務", "接下來最需要 AI 先做哪幾件事？"),
        ),
    ),
    "team_ai": InitializerTemplate(
        key="team_ai",
        label="多人 AI 協作",
        description="適合小組專案，先釐清人員分工，再讓 AI 協助拆任務與追蹤進度。",
        questions=(
            InitializerQuestion("goal", "專案目標", "小組最後要交付什麼成果？"),
            InitializerQuestion("members", "成員與能力", "每個成員擅長什麼？誰負責程式、報告、簡報、資料整理？"),
            InitializerQuestion("decision_owner", "決策方式", "哪些事情由誰拍板？遇到分歧怎麼處理？"),
            InitializerQuestion("ai_role", "AI 參與方式", "AI 要協助管理進度、拆任務、寫程式、整理報告，還是產生分工文件？"),
            InitializerQuestion("workflow", "協作流程", "小組如何交接、確認成果、更新進度？"),
            InitializerQuestion("constraints", "限制條件", "期限、老師要求、組員投入程度、技術限制、成本限制。"),
            InitializerQuestion("next_steps", "下一步任務", "AI 進入專案後應先幫小組完成哪些任務？"),
        ),
    ),
    "capstone": InitializerTemplate(
        key="capstone",
        label="畢業專題開發",
        description="適合畢業專題，強調題目範圍、Demo 價值、文件與可完成性。",
        questions=(
            InitializerQuestion("topic", "專題題目", "專題名稱與一句話說明。"),
            InitializerQuestion("problem", "要解決的問題", "為什麼這個題目值得做？目標使用者遇到什麼痛點？"),
            InitializerQuestion("scope", "第一版範圍", "MVP 必須完成哪些功能？哪些先不做？"),
            InitializerQuestion("tech_stack", "技術方向", "使用哪些語言、框架、資料庫、API 或工具？"),
            InitializerQuestion("demo_value", "Demo 價值", "展示時最想讓老師或同學看到什麼？"),
            InitializerQuestion("documents", "文件與報告", "需要產出哪些文件、簡報、海報或測試紀錄？"),
            InitializerQuestion("risks", "風險與限制", "時程、技術、人力、成本或老師要求的不確定性。"),
            InitializerQuestion("next_steps", "下一步任務", "AI 接下來應先協助規劃、實作或整理哪些內容？"),
        ),
    ),
}


def list_initializer_templates() -> list[InitializerTemplate]:
    return list(INITIALIZER_TEMPLATES.values())


def get_initializer_template(template_key: str) -> InitializerTemplate:
    return INITIALIZER_TEMPLATES[template_key]


def render_initialization_document(
    *,
    project_name: str,
    template_key: str,
    answers: dict[str, str],
) -> str:
    template = get_initializer_template(template_key)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    for question in template.questions:
        answer = answers.get(question.key, "").strip() or "待補"
        sections.append(f"## {question.label}\n\n{answer}")

    question_blocks = "\n\n".join(sections)
    return (
        f"# {project_name} - AI 專案初始化文檔\n\n"
        f"- AI 派工方式：{template.label}\n"
        f"- 產生時間：{created_at}\n\n"
        "## 使用方式\n\n"
        "請把本文件提供給本次專案要操作的 AI，作為專案啟動脈絡。"
        "AI 應先理解本文件，再依照下一步任務開始協作。\n\n"
        "## AI 工作規則\n\n"
        "- 優先根據本文件理解專案目標、限制與分工。\n"
        "- 若需求不清楚，先提出具體問題，不要自行擴大範圍。\n"
        "- 回覆需清楚標示已完成、待確認、下一步。\n"
        "- 涉及檔案或程式修改時，先說明修改目的，再執行可驗證的變更。\n"
        "- 若發現時程、技術或範圍風險，需直接指出並提供可行替代方案。\n\n"
        f"{question_blocks}\n\n"
        "## 給 AI 的啟動指令\n\n"
        "請先閱讀以上專案初始化文檔，整理你目前理解到的專案目標、角色分工、限制條件與下一步。"
        "接著列出你建議的第一輪執行清單，並標示哪些需要使用者確認。\n"
    )
