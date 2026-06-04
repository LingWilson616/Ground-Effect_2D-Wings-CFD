"""Chat widget with streaming markdown display."""

from __future__ import annotations
import re
import html
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QScrollArea, QLabel, QSizePolicy,
)
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound


class StreamWorker(QThread):
    """Worker thread for streaming API calls."""
    chunk_received = Signal(str)
    stream_finished = Signal()
    stream_error = Signal(str)

    def __init__(self, client, messages, parent=None):
        super().__init__(parent)
        self.client = client
        self.messages = messages

    def run(self):
        try:
            stream = self.client.chat_stream(self.messages)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    self.chunk_received.emit(chunk.choices[0].delta.content)
            self.stream_finished.emit()
        except Exception as e:
            self.stream_error.emit(str(e))


class ChatWidget(QWidget):
    """Main chat interface with streaming, markdown, and code highlighting."""

    def __init__(self, ai_client, parent=None):
        super().__init__(parent)
        self.ai_client = ai_client
        self.messages = []
        self.current_response = ""
        self.is_streaming = False
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat display
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: #0d1117;
                border: none;
                padding: 12px;
            }
        """)
        self.chat_display.document().setDefaultStyleSheet("""
            body { color: #c9d1d9; }
            code { background-color: #1c2128; padding: 2px 6px; border-radius: 4px; font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; font-size: 12px; }
            pre { background-color: #1c2128; padding: 16px; border-radius: 8px; border: 1px solid #30363d; overflow-x: auto; }
            pre code { background: none; padding: 0; }
            blockquote { border-left: 3px solid #58a6ff; padding-left: 12px; color: #8b949e; margin: 8px 0; }
            table { border-collapse: collapse; margin: 8px 0; }
            th, td { border: 1px solid #30363d; padding: 6px 12px; }
            th { background: #161b22; }
            a { color: #58a6ff; }
            h1, h2, h3, h4 { color: #f0f6fc; margin-top: 16px; }
            hr { border: none; border-top: 1px solid #30363d; margin: 16px 0; }
            .user-msg { background: #161b22; border-radius: 12px; padding: 12px 16px; margin: 8px 0; }
            .ai-msg { background: #0d1117; border-left: 3px solid #1f6feb; border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 8px 0; }
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # Input area
        input_container = QWidget()
        input_container.setStyleSheet("background-color: #161b22; border-top: 1px solid #30363d;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(10)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入你的CFD问题... (Shift+Enter 换行, Enter 发送)")
        self.input_field.setMaximumHeight(120)
        self.input_field.setMinimumHeight(40)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #1f6feb;
            }
        """)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setFixedSize(64, 38)
        self.send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn, alignment=Qt.AlignBottom)
        layout.addWidget(input_container)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            if not self.is_streaming:
                self._send_message()
            return
        super().keyPressEvent(event)

    def _send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text or self.is_streaming:
            return

        self.input_field.clear()
        self.messages.append({"role": "user", "content": text})
        self._append_message("user", text)
        self.is_streaming = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("...")
        self.current_response = ""

        # Start streaming in worker thread
        self.worker = StreamWorker(self.ai_client, self.messages)
        self.worker.chunk_received.connect(self._on_chunk)
        self.worker.stream_finished.connect(self._on_finished)
        self.worker.stream_error.connect(self._on_error)
        self.worker.start()

    def _on_chunk(self, chunk: str):
        self.current_response += chunk
        self._update_display()

    def _on_finished(self):
        self.messages.append({"role": "assistant", "content": self.current_response})
        self._finalize_display()
        self.is_streaming = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.input_field.setFocus()

    def _on_error(self, error_msg: str):
        self._append_message("system", f"**❌ 错误**: {html.escape(error_msg)}")
        self.is_streaming = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")

    def _append_message(self, role: str, content: str):
        """Append a complete message to the display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        if role == "user":
            header = '<div style="color:#58a6ff;font-size:11px;font-weight:700;margin-bottom:4px;">👤 你</div>'
            body = self._render_markdown(content)
            html_content = f'<div class="user-msg">{header}{body}</div>'
        elif role == "system":
            html_content = f'<div style="color:#f85149;padding:8px;margin:4px 0;">{content}</div>'
        else:
            header = '<div style="color:#7c3aed;font-size:11px;font-weight:700;margin-bottom:4px;">🤖 AI CFD 专家</div>'
            body = self._render_markdown(content)
            html_content = f'<div class="ai-msg">{header}{body}</div>'

        cursor.insertHtml(html_content)
        self.chat_display.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _update_display(self):
        """Update the streaming message in-place."""
        doc = self.chat_display.document()
        # Find and remove the last pending AI message block
        html_doc = self.chat_display.toHtml()
        pending_marker = '<!-- pending -->'
        if pending_marker in html_doc:
            # Remove the pending section and re-add
            idx = html_doc.find(pending_marker)
            # Simple approach: reset and rebuild
            self._rebuild_display()
        else:
            # Add new pending block
            header = '<div style="color:#7c3aed;font-size:11px;font-weight:700;margin-bottom:4px;">🤖 AI CFD 专家</div>'
            body = self._render_markdown(self.current_response)
            html_content = f'<div class="ai-msg">{header}{body}<!-- pending --></div>'

            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml(html_content)
            self.chat_display.setTextCursor(cursor)

        self._scroll_to_bottom()

    def _rebuild_display(self):
        """Full rebuild of chat display (used during streaming)."""
        self.chat_display.clear()
        for msg in self.messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                self._append_message("user", content)
            elif role == "assistant":
                self._append_message("assistant", content)

        # Add pending AI response
        if self.current_response:
            header = '<div style="color:#7c3aed;font-size:11px;font-weight:700;margin-bottom:4px;">🤖 AI CFD 专家</div>'
            body = self._render_markdown(self.current_response)
            html_content = f'<div class="ai-msg">{header}{body}<!-- pending --></div>'
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml(html_content)
            self.chat_display.setTextCursor(cursor)

    def _finalize_display(self):
        """Final render after streaming completes."""
        self._rebuild_display()  # Rebuild cleanly
        # Remove pending marker
        html_doc = self.chat_display.toHtml()
        html_doc = html_doc.replace('<!-- pending -->', '')
        self.chat_display.setHtml(html_doc)
        self._scroll_to_bottom()

    def _render_markdown(self, text: str) -> str:
        """Render markdown text to HTML with syntax highlighting."""
        # Pre-process: find code blocks and highlight them
        def highlight_code(match):
            lang = match.group(1) or ""
            code = match.group(2)
            try:
                if lang:
                    lexer = get_lexer_by_name(lang, stripall=True)
                else:
                    lexer = guess_lexer(code)
            except ClassNotFound:
                lexer = get_lexer_by_name("text", stripall=True)
            formatter = HtmlFormatter(
                style="monokai",
                noclasses=True,
                cssstyles="",
                prestyles="background-color: #1c2128; padding: 16px; border-radius: 8px; border: 1px solid #30363d; overflow-x: auto; margin: 8px 0;",
            )
            highlighted = highlight(code, lexer, formatter)
            return highlighted

        text = re.sub(r'```(\w*)\n(.*?)```', highlight_code, text, flags=re.DOTALL)

        # Convert markdown to HTML
        md = markdown.Markdown(extensions=['fenced_code', 'tables', 'codehilite', 'nl2br'])
        html_body = md.convert(text)

        # Fix inline LaTeX: $...$ → styled span
        html_body = re.sub(
            r'\$\$(.+?)\$\$',
            r'<div style="background:#161b22;padding:12px 16px;border-left:3px solid #d2a8ff;margin:8px 0;font-family:serif;font-style:italic;">\1</div>',
            html_body
        )
        html_body = re.sub(
            r'\$(.+?)\$',
            r'<code style="background:#161b22;color:#d2a8ff;font-style:italic;">\1</code>',
            html_body
        )

        return html_body

    def _scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_chat(self):
        self.messages.clear()
        self.current_response = ""
        self.chat_display.clear()
