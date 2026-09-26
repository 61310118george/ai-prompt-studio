from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_memory_app.data.models import MemoryItem
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.ai_client import AIClientError, organize_with_openai, revise_markdown_with_openai
from ai_memory_app.services.exporter import export_memory_csv, export_prompt_markdown
from ai_memory_app.services.markdown_workspace import (
    MarkdownFile,
    MarkdownProject,
    build_unified_diff,
    list_markdown_files,
    list_projects,
    offline_revise_markdown,
    read_markdown,
    write_markdown,
)
from ai_memory_app.services.project_initializer import (
    get_initializer_template,
    list_initializer_templates,
    render_initialization_document,
)
from ai_memory_app.services.prompt_builder import render_tool_prompt


MAIN_AREAS = [
    ("project_initializer", "專案初始化"),
    ("folder_memory", "資料夾記憶"),
    ("about_me", "關於我"),
    ("project_memory", "專案記憶"),
    ("prompt_library", "提示詞庫"),
    ("ai_organizer", "AI 整理器"),
]

DEFAULT_CATEGORIES = {
    "about_me": [
        ("personal_background", "個人背景"),
        ("technical_skills", "技術能力"),
        ("preferences_constraints", "偏好與限制"),
        ("ai_personality", "AI 個性設定"),
        ("workflow_style", "常用工作方式"),
        ("avoidance", "不想碰的技術或功能"),
    ],
    "project_memory": [
        ("project_background", "專案背景"),
        ("project_requirements", "專案需求"),
        ("decision_record", "決策紀錄"),
        ("risk_note", "風險與注意事項"),
        ("next_action", "下一步任務"),
    ],
    "prompt_library": [
        ("common_prompt", "常用提示詞"),
        ("prompt_template", "提示詞模板"),
        ("reusable_snippet", "可重複使用片段"),
        ("output_pattern", "輸出範本"),
    ],
}

SECTION_HINTS = {
    "project_initializer": "用預設問題建立新專案 AI 協作脈絡，產出可直接交給 AI 的 Markdown 啟動文檔。",
    "folder_memory": "選擇一個 AI 記憶根資料夾，讀取底下的專案資料夾與 Markdown 檔，先預覽 diff 再寫回檔案。",
    "about_me": "記錄你的背景、技術能力、偏好、限制與 AI 個性設定，讓不同 AI 更快理解你。",
    "project_memory": "記錄畢業專題的背景、需求、決策、風險與下一步，方便報告與後續開發追蹤。",
    "prompt_library": "集中管理常用提示詞、模板、可重複使用片段與輸出範本。",
    "ai_organizer": "把零散內容整理成可保存的記憶或提示詞；可離線整理，也可填 API Key 呼叫 AI。",
}


class MainWindow(QMainWindow):
    def __init__(self, repository: MemoryRepository) -> None:
        super().__init__()
        self.repository = repository
        self.current_main_area = "folder_memory"
        self.current_item: MemoryItem | None = None
        self.workspace_root: Path | None = None
        self.current_project: MarkdownProject | None = None
        self.current_markdown_file: MarkdownFile | None = None
        self.original_markdown = ""
        self.revised_markdown = ""
        self.initializer_question_edits: dict[str, QTextEdit] = {}

        self.setWindowTitle("AI 個人化記憶管理系統")
        self.setCentralWidget(self._build_root())
        self._apply_styles()
        self._select_main_area("project_initializer")
        self._load_tool_templates()

    def _build_root(self) -> QWidget:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        nav = self._build_navigation()
        self.stack = QStackedWidget()
        self.initializer_page = self._build_project_initializer_page()
        self.folder_page = self._build_folder_memory_page()
        self.memory_page = self._build_memory_page()
        self.organizer_page = self._build_organizer_page()

        self.stack.addWidget(self.initializer_page)
        self.stack.addWidget(self.folder_page)
        self.stack.addWidget(self.memory_page)
        self.stack.addWidget(self.organizer_page)

        root_layout.addWidget(nav)
        root_layout.addWidget(self.stack, 1)
        return root

    def _build_navigation(self) -> QWidget:
        nav = QWidget()
        nav.setObjectName("sidebar")
        nav.setFixedWidth(210)
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(10)

        title = QLabel("AI Memory")
        title.setObjectName("appTitle")
        subtitle = QLabel("個人化記憶管理")
        subtitle.setObjectName("mutedLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in MAIN_AREAS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("navButton")
            button.setToolTip(SECTION_HINTS.get(key, label))
            button.clicked.connect(lambda checked=False, area=key: self._select_main_area(area))
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.api_status = QLabel("AI API：未設定")
        self.api_status.setObjectName("mutedLabel")
        layout.addWidget(self.api_status)
        return nav

    def _build_project_initializer_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("專案初始化")
        title.setObjectName("sectionTitle")
        hint = QLabel("先設定 AI 派工方式與預設問題，產出一份可直接交給新專案 AI 的啟動文檔。")
        hint.setObjectName("mutedLabel")
        header.addWidget(title)
        header.addWidget(hint, 1)
        layout.addLayout(header)

        controls = QVBoxLayout()
        project_row = QHBoxLayout()
        self.initializer_project_name = QLineEdit()
        self.initializer_project_name.setPlaceholderText("專案名稱")
        self.initializer_project_name.setText("新專案")
        self.initializer_project_name.setMinimumWidth(520)
        self.initializer_project_name.setMinimumHeight(46)
        self.initializer_template_combo = QComboBox()
        self.initializer_template_combo.setMinimumWidth(260)
        for template in list_initializer_templates():
            self.initializer_template_combo.addItem(template.label, template.key)
        self.initializer_template_combo.currentIndexChanged.connect(self._rebuild_initializer_questions)
        self.generate_initializer_button = QPushButton("產生初始化文檔")
        self.generate_initializer_button.setObjectName("primaryButton")
        self.generate_initializer_button.clicked.connect(self._generate_initialization_document)
        self.save_initializer_button = QPushButton("保存到提示詞庫")
        self.save_initializer_button.clicked.connect(self._save_initialization_to_prompt_library)
        self.export_initializer_button = QPushButton("匯出 Markdown")
        self.export_initializer_button.clicked.connect(self._export_initialization_markdown)

        project_row.addWidget(QLabel("專案"))
        project_row.addWidget(self.initializer_project_name, 1)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("AI 派工方式"))
        action_row.addWidget(self.initializer_template_combo)
        action_row.addStretch(1)
        action_row.addWidget(self.generate_initializer_button)
        action_row.addWidget(self.save_initializer_button)
        action_row.addWidget(self.export_initializer_button)
        controls.addLayout(project_row)
        controls.addLayout(action_row)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.initializer_template_description = QLabel("")
        self.initializer_template_description.setObjectName("hintLabel")
        self.initializer_template_description.setWordWrap(True)
        left_layout.addWidget(self.initializer_template_description)

        self.initializer_question_container = QWidget()
        self.initializer_question_form = QFormLayout(self.initializer_question_container)
        self.initializer_question_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.initializer_question_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.initializer_question_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.initializer_question_form.setHorizontalSpacing(18)
        self.initializer_question_form.setVerticalSpacing(14)
        self.initializer_question_form.setContentsMargins(8, 8, 8, 8)

        question_scroll = QScrollArea()
        question_scroll.setWidgetResizable(True)
        question_scroll.setWidget(self.initializer_question_container)
        left_layout.addWidget(question_scroll, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(QLabel("初始化文檔預覽"))
        self.initializer_output = QTextEdit()
        self.initializer_output.setPlaceholderText("填寫左側問題後，點擊「產生初始化文檔」。")
        right_layout.addWidget(self.initializer_output, 1)
        splitter.addWidget(right)
        splitter.setSizes([520, 680])

        layout.addWidget(splitter, 1)
        self._rebuild_initializer_questions()
        return page

    def _build_folder_memory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("資料夾記憶")
        title.setObjectName("sectionTitle")
        self.root_label = QLabel("尚未選擇根資料夾")
        self.root_label.setObjectName("mutedLabel")
        self.choose_root_button = QPushButton("選擇根資料夾")
        self.choose_root_button.setObjectName("primaryButton")
        self.choose_root_button.clicked.connect(self._choose_workspace_root)
        self.refresh_workspace_button = QPushButton("重新讀取")
        self.refresh_workspace_button.clicked.connect(self._refresh_workspace)
        header.addWidget(title)
        header.addWidget(self.root_label, 1)
        header.addWidget(self.choose_root_button)
        header.addWidget(self.refresh_workspace_button)
        layout.addLayout(header)

        self.progress_label = QLabel("等待操作")
        self.progress_label.setObjectName("mutedLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(QLabel("專案資料夾"))
        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        left_layout.addWidget(self.project_list, 1)
        left_layout.addWidget(QLabel("Markdown 記憶檔"))
        self.markdown_list = QListWidget()
        self.markdown_list.currentItemChanged.connect(self._on_markdown_selected)
        left_layout.addWidget(self.markdown_list, 2)
        splitter.addWidget(left)

        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(10)
        middle_layout.addWidget(QLabel("目前 Markdown"))
        self.markdown_editor = QTextEdit()
        self.markdown_editor.setPlaceholderText("選擇左側 .md 檔後，內容會顯示在這裡。")
        middle_layout.addWidget(self.markdown_editor, 3)
        middle_layout.addWidget(QLabel("修改指令"))
        self.change_instruction = QTextEdit()
        self.change_instruction.setFixedHeight(96)
        self.change_instruction.setPlaceholderText("例：把這份提示詞改成更適合 Codex，並保留我的技術限制。")
        middle_layout.addWidget(self.change_instruction)

        action_row = QHBoxLayout()
        self.folder_api_key_input = QLineEdit()
        self.folder_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.folder_api_key_input.setPlaceholderText("OpenAI API Key（可選，不保存）")
        self.folder_model_input = QLineEdit("gpt-5.2")
        self.folder_model_input.setFixedWidth(110)
        self.preview_change_button = QPushButton("產生變更預覽")
        self.preview_change_button.setObjectName("primaryButton")
        self.preview_change_button.clicked.connect(self._preview_markdown_change)
        self.apply_change_button = QPushButton("套用到 md 檔")
        self.apply_change_button.clicked.connect(self._apply_markdown_change)
        action_row.addWidget(self.folder_api_key_input)
        action_row.addWidget(QLabel("Model"))
        action_row.addWidget(self.folder_model_input)
        action_row.addWidget(self.preview_change_button)
        action_row.addWidget(self.apply_change_button)
        middle_layout.addLayout(action_row)
        splitter.addWidget(middle)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(QLabel("新版預覽"))
        self.revised_editor = QTextEdit()
        self.revised_editor.setPlaceholderText("AI 或離線整理產生的新版本會顯示在這裡。")
        right_layout.addWidget(self.revised_editor, 2)
        right_layout.addWidget(QLabel("變更摘要 / Diff"))
        self.diff_viewer = QTextEdit()
        self.diff_viewer.setReadOnly(True)
        self.diff_viewer.setPlaceholderText("這裡會用類似 code diff 的方式顯示修改內容。")
        right_layout.addWidget(self.diff_viewer, 2)
        splitter.addWidget(right)

        splitter.setSizes([260, 560, 520])
        layout.addWidget(splitter, 1)
        return page

    def _build_memory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.section_title = QLabel("關於我")
        self.section_title.setObjectName("sectionTitle")
        self.new_button = QPushButton("新增記憶")
        self.new_button.clicked.connect(self._new_memory_item)
        self.delete_button = QPushButton("刪除")
        self.delete_button.clicked.connect(self._delete_memory_item)
        self.versions_button = QPushButton("版本")
        self.versions_button.setToolTip("查看目前記憶的歷史版本與修改摘要。")
        self.versions_button.clicked.connect(self._show_versions)
        self.export_csv_button = QPushButton("備份成 CSV")
        self.export_csv_button.setToolTip("把目前區塊的記憶資料匯出成 CSV，方便用 Excel、Numbers 或資料庫工具檢查與備份。")
        self.export_csv_button.clicked.connect(self._export_memory_csv)
        self.save_button = QPushButton("儲存")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self._save_memory_item)
        header.addWidget(self.section_title)
        header.addStretch(1)
        header.addWidget(self.new_button)
        header.addWidget(self.delete_button)
        header.addWidget(self.versions_button)
        header.addWidget(self.export_csv_button)
        header.addWidget(self.save_button)
        layout.addLayout(header)

        self.section_hint = QLabel("")
        self.section_hint.setObjectName("hintLabel")
        self.section_hint.setWordWrap(True)
        layout.addWidget(self.section_hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.item_list = QListWidget()
        self.item_list.currentItemChanged.connect(self._on_item_selected)
        splitter.addWidget(self.item_list)

        editor = QWidget()
        form = QFormLayout(editor)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(18)
        form.setContentsMargins(8, 6, 8, 6)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(260)
        self.category_combo.setMinimumHeight(42)
        self.category_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.category_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.category_combo.view().setMinimumWidth(280)
        self.title_edit = QLineEdit()
        self.content_edit = QTextEdit()
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("例：collaboration, codex, report")
        self.importance_spin = QSpinBox()
        self.importance_spin.setRange(1, 5)
        self.importance_spin.setValue(3)
        self.enabled_check = QCheckBox("輸出時啟用")
        self.enabled_check.setChecked(True)

        form.addRow("分類", self.category_combo)
        form.addRow("標題", self.title_edit)
        form.addRow("內容", self.content_edit)
        form.addRow("標籤", self.tags_edit)
        form.addRow("重要程度", self.importance_spin)
        form.addRow("", self.enabled_check)

        splitter.addWidget(editor)
        splitter.setSizes([360, 760])
        layout.addWidget(splitter, 1)
        return page

    def _build_organizer_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("AI 整理器")
        title.setObjectName("sectionTitle")
        hint = QLabel("沒有 API Key 時使用離線整理；填入 API Key 後可呼叫 OpenAI Responses API。API Key 不會保存。")
        hint.setObjectName("mutedLabel")

        self.organizer_input = QTextEdit()
        self.organizer_input.setPlaceholderText("貼上長篇、零散或口語化內容...")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("OpenAI API Key（可選，不保存）")
        self.model_input = QLineEdit("gpt-5.2")
        self.model_input.setPlaceholderText("Model")
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem("內部記憶格式", "internal")
        self.output_format_combo.addItem("Codex", "codex")
        self.output_format_combo.addItem("通用 ChatGPT", "chatgpt")
        self.output_format_combo.addItem("Claude", "claude")
        self.convert_button = QPushButton("產生草稿")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.clicked.connect(self._generate_draft)
        self.generate_prompt_button = QPushButton("從啟用記憶產生提示詞")
        self.generate_prompt_button.clicked.connect(self._generate_prompt_from_memory)
        self.save_draft_button = QPushButton("保存到提示詞庫")
        self.save_draft_button.clicked.connect(self._save_draft_to_prompt_library)
        self.export_prompt_button = QPushButton("匯出 Markdown")
        self.export_prompt_button.clicked.connect(self._export_prompt_markdown)
        self.organizer_output = QTextEdit()
        self.organizer_output.setPlaceholderText("整理後的草稿會顯示在這裡。")

        controls = QHBoxLayout()
        controls.addWidget(QLabel("API Key"))
        controls.addWidget(self.api_key_input)
        controls.addWidget(QLabel("Model"))
        controls.addWidget(self.model_input)
        controls.addWidget(QLabel("輸出格式"))
        controls.addWidget(self.output_format_combo)
        controls.addStretch(1)
        controls.addWidget(self.generate_prompt_button)
        controls.addWidget(self.convert_button)
        controls.addWidget(self.save_draft_button)
        controls.addWidget(self.export_prompt_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.organizer_input, 2)
        layout.addLayout(controls)
        layout.addWidget(self.organizer_output, 2)
        return page

    def _select_main_area(self, main_area: str) -> None:
        self.current_main_area = main_area
        for key, button in self.nav_buttons.items():
            button.setChecked(key == main_area)

        if main_area == "project_initializer":
            self.stack.setCurrentWidget(self.initializer_page)
            return

        if main_area == "folder_memory":
            self.stack.setCurrentWidget(self.folder_page)
            return

        if main_area == "ai_organizer":
            self.stack.setCurrentWidget(self.organizer_page)
            return

        self.stack.setCurrentWidget(self.memory_page)
        self.section_title.setText(dict(MAIN_AREAS)[main_area])
        self.section_hint.setText(SECTION_HINTS.get(main_area, ""))
        self._load_categories(main_area)
        self._load_memory_items(main_area)

    def _rebuild_initializer_questions(self) -> None:
        while self.initializer_question_form.rowCount() > 0:
            self.initializer_question_form.removeRow(0)
        self.initializer_question_edits.clear()

        template_key = str(self.initializer_template_combo.currentData())
        template = get_initializer_template(template_key)
        self.initializer_template_description.setText(template.description)

        for question in template.questions:
            edit = QTextEdit()
            edit.setFixedHeight(86)
            edit.setPlaceholderText(question.placeholder)
            self.initializer_question_edits[question.key] = edit
            self.initializer_question_form.addRow(question.label, edit)

    def _collect_initializer_answers(self) -> dict[str, str]:
        return {
            key: edit.toPlainText().strip()
            for key, edit in self.initializer_question_edits.items()
        }

    def _generate_initialization_document(self) -> None:
        project_name = self.initializer_project_name.text().strip()
        if not project_name:
            QMessageBox.warning(self, "缺少專案名稱", "請先輸入專案名稱。")
            self.initializer_project_name.setFocus()
            return

        template_key = str(self.initializer_template_combo.currentData())
        document = render_initialization_document(
            project_name=project_name,
            template_key=template_key,
            answers=self._collect_initializer_answers(),
        )
        self.initializer_output.setPlainText(document)
        self.repository.record_ai_processing_run(
            input_text=f"project_initializer:{template_key}",
            processing_goal="project_initialization",
            target_category=template_key,
            output_format="markdown",
            used_api=False,
            output_text=document,
        )

    def _save_initialization_to_prompt_library(self) -> None:
        content = self.initializer_output.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "沒有文檔", "請先產生初始化文檔。")
            return
        project_name = self.initializer_project_name.text().strip() or "新專案"
        template_key = str(self.initializer_template_combo.currentData())
        item_id = self.repository.create_memory_item(
            main_area="prompt_library",
            category="prompt_template",
            title=f"{project_name} - AI 專案初始化文檔",
            content=content,
            tags=f"project-initializer,{template_key}",
            source="project_initializer",
        )
        QMessageBox.information(self, "已保存", f"已保存到提示詞庫，ID：{item_id}")

    def _export_initialization_markdown(self) -> None:
        content = self.initializer_output.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "沒有文檔", "請先產生初始化文檔。")
            return
        project_name = self.initializer_project_name.text().strip() or "new_project"
        safe_name = "".join(char if char.isalnum() else "_" for char in project_name).strip("_") or "new_project"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "匯出專案初始化 Markdown",
            f"{safe_name}_ai_initialization.md",
            "Markdown Files (*.md);;Text Files (*.txt)",
        )
        if not file_name:
            return
        export_prompt_markdown(content, Path(file_name))
        self.repository.record_export(
            export_type="project_initialization",
            output_format="markdown",
            file_path=file_name,
            item_count=1,
        )
        QMessageBox.information(self, "匯出完成", "專案初始化文檔已匯出。")

    def _set_progress(self, text: str, value: int) -> None:
        self.progress_label.setText(text)
        self.progress_bar.setValue(value)

    def _choose_workspace_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇 AI 記憶根資料夾")
        if not folder:
            return
        self.workspace_root = Path(folder)
        self.root_label.setText(str(self.workspace_root))
        self._refresh_workspace()

    def _refresh_workspace(self) -> None:
        self.project_list.clear()
        self.markdown_list.clear()
        self.markdown_editor.clear()
        self.revised_editor.clear()
        self.diff_viewer.clear()
        if self.workspace_root is None:
            self._set_progress("請先選擇根資料夾", 0)
            return
        projects = list_projects(self.workspace_root)
        for project in projects:
            item = QListWidgetItem(project.name)
            item.setData(Qt.ItemDataRole.UserRole, project)
            self.project_list.addItem(item)
        self._set_progress(f"已讀取 {len(projects)} 個專案資料夾", 20 if projects else 5)
        if self.project_list.count() > 0:
            self.project_list.setCurrentRow(0)

    def _on_project_selected(self, current: QListWidgetItem | None) -> None:
        self.markdown_list.clear()
        self.markdown_editor.clear()
        self.revised_editor.clear()
        self.diff_viewer.clear()
        if current is None:
            return
        project = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(project, MarkdownProject):
            return
        self.current_project = project
        files = list_markdown_files(project.path)
        for markdown_file in files:
            item = QListWidgetItem(markdown_file.relative_path)
            item.setData(Qt.ItemDataRole.UserRole, markdown_file)
            self.markdown_list.addItem(item)
        self._set_progress(f"已讀取 {project.name}：{len(files)} 個 Markdown 檔", 35 if files else 20)
        if self.markdown_list.count() > 0:
            self.markdown_list.setCurrentRow(0)

    def _on_markdown_selected(self, current: QListWidgetItem | None) -> None:
        self.revised_editor.clear()
        self.diff_viewer.clear()
        self.revised_markdown = ""
        if current is None:
            return
        markdown_file = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(markdown_file, MarkdownFile):
            return
        self.current_markdown_file = markdown_file
        try:
            self.original_markdown = read_markdown(markdown_file.path)
        except OSError as exc:
            QMessageBox.warning(self, "讀取失敗", str(exc))
            return
        self.markdown_editor.setPlainText(self.original_markdown)
        self._set_progress(f"已載入 {markdown_file.relative_path}", 45)

    def _preview_markdown_change(self) -> None:
        if self.current_markdown_file is None:
            QMessageBox.warning(self, "尚未選擇檔案", "請先選擇一個 Markdown 檔。")
            return
        current_text = self.markdown_editor.toPlainText()
        instruction = self.change_instruction.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(self, "缺少修改指令", "請輸入你想如何修改這份 Markdown。")
            return

        api_key = self.folder_api_key_input.text().strip()
        self._set_progress("正在產生變更預覽", 60)
        try:
            if api_key:
                revised = revise_markdown_with_openai(
                    api_key=api_key,
                    model=self.folder_model_input.text().strip() or "gpt-5.2",
                    markdown_text=current_text,
                    instruction=instruction,
                    file_name=self.current_markdown_file.name,
                )
            else:
                revised = offline_revise_markdown(current_text, instruction)
        except AIClientError as exc:
            self._set_progress("AI 修改失敗", 0)
            QMessageBox.warning(self, "AI 修改失敗", str(exc))
            return

        self.revised_markdown = revised
        diff = build_unified_diff(current_text, revised, filename=self.current_markdown_file.relative_path)
        self.revised_editor.setPlainText(revised)
        self.diff_viewer.setPlainText(diff or "沒有偵測到文字差異。")
        self._set_progress("變更預覽完成，請檢查 diff 後再套用", 82)

    def _apply_markdown_change(self) -> None:
        if self.current_markdown_file is None:
            QMessageBox.warning(self, "尚未選擇檔案", "請先選擇一個 Markdown 檔。")
            return
        revised = self.revised_editor.toPlainText().strip()
        if not revised:
            QMessageBox.warning(self, "沒有新版內容", "請先產生變更預覽。")
            return
        result = QMessageBox.question(
            self,
            "確認套用",
            f"確定要把新版內容寫入 {self.current_markdown_file.relative_path}？",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            write_markdown(self.current_markdown_file.path, revised + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "寫入失敗", str(exc))
            return
        self.original_markdown = revised
        self.markdown_editor.setPlainText(revised)
        self._set_progress("已套用修改到 Markdown 檔", 100)
        QMessageBox.information(self, "已套用", "Markdown 檔已更新。")

    def _load_categories(self, main_area: str) -> None:
        self.category_combo.clear()
        for key, label in DEFAULT_CATEGORIES.get(main_area, []):
            self.category_combo.addItem(label, key)

    def _load_memory_items(self, main_area: str) -> None:
        self._load_categories(main_area)
        self.item_list.clear()
        items = self.repository.list_memory_items(main_area)
        for item in items:
            list_item = QListWidgetItem(f"{item.title}\n{item.category}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.item_list.addItem(list_item)
        if self.item_list.count() > 0:
            self.item_list.setCurrentRow(0)
        else:
            self._clear_editor()

    def _load_tool_templates(self) -> None:
        templates = self.repository.list_tool_templates()
        if templates:
            self.api_status.setText(f"內建模板：{len(templates)} 種")

    def _on_item_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        item = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(item, MemoryItem):
            return
        self.current_item = item
        index = self.category_combo.findData(item.category)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        self.title_edit.setText(item.title)
        self.content_edit.setPlainText(item.content)
        self.tags_edit.setText(item.tags or "")
        self.importance_spin.setValue(item.importance)
        self.enabled_check.setChecked(item.enabled)

    def _new_memory_item(self) -> None:
        self.current_item = None
        self._clear_editor()
        self.title_edit.setFocus()

    def _save_memory_item(self) -> None:
        if self.current_main_area == "ai_organizer":
            return

        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        category = self.category_combo.currentData()
        tags = self.tags_edit.text().strip()

        if not title or not content or not category:
            QMessageBox.warning(self, "資料不足", "標題、分類與內容都必須填寫。")
            return

        if self.current_item is None:
            saved_id = self.repository.create_memory_item(
                main_area=self.current_main_area,
                category=category,
                title=title,
                content=content,
                tags=tags,
                importance=self.importance_spin.value(),
                enabled=self.enabled_check.isChecked(),
            )
        else:
            saved_id = self.current_item.id
            self.repository.update_memory_item(
                self.current_item.id,
                category=category,
                title=title,
                content=content,
                tags=tags,
                importance=self.importance_spin.value(),
                enabled=self.enabled_check.isChecked(),
            )
        self._load_memory_items(self.current_main_area)
        self._select_item_by_id(saved_id)

    def _select_item_by_id(self, memory_item_id: int) -> None:
        for index in range(self.item_list.count()):
            item = self.item_list.item(index).data(Qt.ItemDataRole.UserRole)
            if isinstance(item, MemoryItem) and item.id == memory_item_id:
                self.item_list.setCurrentRow(index)
                return

    def _delete_memory_item(self) -> None:
        if self.current_item is None:
            QMessageBox.information(self, "尚未選擇", "請先選擇要刪除的記憶。")
            return
        result = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除「{self.current_item.title}」？此操作會一併刪除版本紀錄。",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self.repository.delete_memory_item(self.current_item.id)
        self.current_item = None
        self._load_memory_items(self.current_main_area)

    def _show_versions(self) -> None:
        if self.current_item is None:
            QMessageBox.information(self, "尚未選擇", "請先選擇記憶。")
            return
        versions = self.repository.list_versions(self.current_item.id)
        if not versions:
            QMessageBox.information(self, "沒有版本紀錄", "目前沒有版本紀錄。")
            return
        lines: list[str] = []
        for version in versions[:12]:
            lines.append(
                f"v{version.version_number} | {version.changed_by} | {version.created_at}\n"
                f"{version.change_summary or ''}\n"
            )
        QMessageBox.information(self, "版本紀錄", "\n".join(lines))

    def _export_memory_csv(self) -> None:
        items = self.repository.list_memory_items(self.current_main_area)
        if not items:
            QMessageBox.information(self, "沒有資料", "目前區域沒有可匯出的記憶。")
            return
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "匯出記憶 CSV",
            f"{self.current_main_area}_memory.csv",
            "CSV Files (*.csv)",
        )
        if not file_name:
            return
        export_memory_csv(items, Path(file_name))
        self.repository.record_export(
            export_type="memory_items",
            output_format="csv",
            file_path=file_name,
            item_count=len(items),
        )
        QMessageBox.information(self, "匯出完成", f"已匯出 {len(items)} 筆資料。")

    def _clear_editor(self) -> None:
        self.title_edit.clear()
        self.content_edit.clear()
        self.tags_edit.clear()
        self.importance_spin.setValue(3)
        self.enabled_check.setChecked(True)

    def _generate_draft(self) -> None:
        source = self.organizer_input.toPlainText().strip()
        output_format = self.output_format_combo.currentText()
        if not source:
            QMessageBox.warning(self, "沒有輸入內容", "請先貼上要整理的內容。")
            return
        api_key = self.api_key_input.text().strip()
        used_api = False
        try:
            if api_key:
                self.convert_button.setEnabled(False)
                self.convert_button.setText("整理中...")
                draft = organize_with_openai(
                    api_key=api_key,
                    model=self.model_input.text().strip() or "gpt-5.2",
                    source_text=source,
                    output_format=output_format,
                )
                used_api = True
            else:
                compact_lines = [line.strip() for line in source.splitlines() if line.strip()]
                compact_text = "\n".join(f"- {line}" for line in compact_lines)
                draft = (
                    f"輸出格式：{output_format}\n\n"
                    "整理草稿：\n"
                    f"{compact_text}\n\n"
                    "目前為離線整理模式；填入 API Key 後可自動摘要、分類與重寫。"
                )
        except AIClientError as exc:
            QMessageBox.warning(self, "AI API 失敗", str(exc))
            self.repository.record_ai_processing_run(
                input_text=source,
                processing_goal="prompt",
                target_category=None,
                output_format=str(self.output_format_combo.currentData()),
                used_api=True,
                output_text="",
                status="failed",
                error_message=str(exc),
            )
            return
        finally:
            self.convert_button.setEnabled(True)
            self.convert_button.setText("產生草稿")
        self.organizer_output.setPlainText(draft)
        self.repository.record_ai_processing_run(
            input_text=source,
            processing_goal="prompt",
            target_category=None,
            output_format=str(self.output_format_combo.currentData()),
            used_api=used_api,
            output_text=draft,
        )

    def _generate_prompt_from_memory(self) -> None:
        tool_key = str(self.output_format_combo.currentData())
        all_items = self.repository.list_memory_items()
        if tool_key == "internal":
            content = "\n\n".join(f"## {item.title}\n{item.content}" for item in all_items if item.enabled)
        else:
            template = self.repository.get_tool_template(tool_key)
            if template is None:
                QMessageBox.warning(self, "模板不存在", "找不到指定的工具模板。")
                return
            content = render_tool_prompt(tool_key, template["template_content"], all_items)
        self.organizer_output.setPlainText(content)
        self.repository.record_ai_processing_run(
            input_text="enabled_memory_items",
            processing_goal="prompt",
            target_category=None,
            output_format=tool_key,
            used_api=False,
            output_text=content,
        )

    def _save_draft_to_prompt_library(self) -> None:
        content = self.organizer_output.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "沒有草稿", "請先產生或輸入整理結果。")
            return
        item_id = self.repository.create_memory_item(
            main_area="prompt_library",
            category="prompt_template",
            title="AI 整理器草稿",
            content=content,
            tags="ai-organizer,draft",
            source="ai_organizer",
        )
        QMessageBox.information(self, "已保存", f"已保存到提示詞庫，ID：{item_id}")

    def _export_prompt_markdown(self) -> None:
        content = self.organizer_output.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "沒有內容", "請先產生要匯出的提示詞。")
            return
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 Markdown",
            "ai_prompt.md",
            "Markdown Files (*.md);;Text Files (*.txt)",
        )
        if not file_name:
            return
        export_prompt_markdown(content, Path(file_name))
        self.repository.record_export(
            export_type="tool_output",
            output_format="markdown",
            file_path=file_name,
            item_count=1,
        )
        QMessageBox.information(self, "匯出完成", "提示詞已匯出。")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #F7F1E8;
                color: #2B2118;
            }
            QWidget {
                color: #2B2118;
                selection-background-color: #E8D8C3;
                selection-color: #2B2118;
            }
            QWidget#sidebar {
                background: #EFE3D2;
                border-right: 1px solid #D8C6AE;
            }
            QLabel#appTitle {
                font-size: 21px;
                font-weight: 700;
                color: #3A2A1C;
            }
            QLabel#sectionTitle {
                font-size: 23px;
                font-weight: 700;
                color: #3A2A1C;
            }
            QLabel#mutedLabel {
                color: #735F49;
                font-size: 12px;
            }
            QLabel#hintLabel {
                color: #5E4A37;
                font-size: 13px;
                line-height: 1.45;
                padding: 8px 10px;
                background: #FFF9F0;
                border: 1px solid #E1CFB7;
                border-radius: 10px;
            }
            QPushButton {
                min-height: 34px;
                padding: 7px 14px;
                border-radius: 9px;
                border: 1px solid #CBB89F;
                background: #FFF9F0;
                color: #3A2A1C;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F4E6D3;
            }
            QPushButton#primaryButton {
                background: #8A6442;
                color: #FFFFFF;
                border: 1px solid #8A6442;
            }
            QPushButton#primaryButton:hover {
                background: #745236;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                background: #E8DED1;
                color: #8A7C6B;
                border: 1px solid #D8CABB;
            }
            QPushButton#navButton {
                text-align: left;
                border: 0;
                background: transparent;
                padding: 10px 12px;
                color: #4A3827;
                border-radius: 10px;
            }
            QPushButton#navButton:checked {
                background: #D9C3A8;
                color: #2B2118;
                font-weight: 600;
            }
            QPushButton#navButton:hover {
                background: #E7D7C1;
            }
            QListWidget, QTextEdit, QLineEdit, QComboBox, QSpinBox {
                background: #FFFDF8;
                color: #2B2118;
                border: 1px solid #D8C6AE;
                border-radius: 10px;
                selection-background-color: #E8D8C3;
                selection-color: #2B2118;
            }
            QComboBox QAbstractItemView {
                background: #FFFDF8;
                color: #2B2118;
                selection-background-color: #E8D8C3;
                selection-color: #2B2118;
            }
            QScrollArea {
                background: transparent;
                border: 0;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #EFE2D2;
                color: #2B2118;
                background: #FFFDF8;
            }
            QListWidget::item:selected {
                background: #E8D8C3;
                color: #2B2118;
            }
            QListWidget::item:hover {
                background: #F4E9DA;
                color: #2B2118;
            }
            QTextEdit {
                padding: 12px;
                font-size: 13px;
                color: #2B2118;
                background: #FFFDF8;
            }
            QLineEdit {
                padding: 8px 10px;
                font-size: 13px;
                color: #2B2118;
                background: #FFFDF8;
                min-height: 38px;
            }
            QComboBox {
                padding: 8px 38px 8px 12px;
                font-size: 13px;
                color: #2B2118;
                background: #FFFDF8;
                min-height: 40px;
                min-width: 260px;
            }
            QComboBox::drop-down {
                width: 32px;
                border-left: 1px solid #D8C6AE;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
                background: #F4E6D3;
            }
            QComboBox QAbstractItemView {
                background: #FFFDF8;
                color: #2B2118;
                selection-background-color: #E8D8C3;
                selection-color: #2B2118;
                outline: 0;
                padding: 6px;
                min-width: 280px;
            }
            QSpinBox {
                min-height: 38px;
                padding: 6px 8px;
            }
            QCheckBox {
                color: #2B2118;
            }
            QCheckBox:disabled {
                color: #8A7C6B;
            }
            QProgressBar {
                border: 1px solid #D8C6AE;
                border-radius: 8px;
                background: #FFFDF8;
                color: #2B2118;
                min-height: 16px;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: #B58B5F;
            }
            """
        )
        self.nav_buttons["project_initializer"].setChecked(True)
