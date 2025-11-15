# /ryas_ui/main_window.py - VERSÃO FINAL (COM TOGGLE SWITCH)

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QWidget):
    def __init__(self, ryas_core):
        super().__init__()
        self.ryas_core = ryas_core
        self.dragPos = None
        self.setup_assets()
        self.setup_ui()
        self.connect_signals()

    def setup_assets(self):
        # ... (função sem alteração)
        assets_path = Path(__file__).parent.parent / "assets"
        idle_path = assets_path / "idle.png"
        listening_path = assets_path / "listening.gif"
        thinking_path = assets_path / "thinking.gif"
        speaking_path = assets_path / "speaking.gif"
        if idle_path.is_file():
            self.idle_pixmap = QPixmap(str(idle_path))
        else:
            print(f"ERRO: Arquivo 'idle.png' NÃO ENCONTRADO em {idle_path}!")
            self.idle_pixmap = None
        self.listening_movie = QMovie(str(listening_path))
        self.thinking_movie = QMovie(str(thinking_path))
        self.speaking_movie = QMovie(str(speaking_path))
        self.current_state = "idle"

    def setup_ui(self):
        self.setWindowTitle("Ryas, a Assistente Carmesim")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(350, 450)

        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        window_layout.addWidget(self.main_frame)

        # --- INÍCIO DA MUDANÇA: NOVO ESTILO DO QCHECKBOX ---
        self.main_frame.setStyleSheet("""
            #MainFrame {
                background-color: rgba(25, 25, 35, 240);
                border-radius: 20px;
            }
            #ResponseLabel {
                color: #E0E0E0;
                font-size: 14px;
                padding: 10px;
                background-color: rgba(0,0,0,0.1);
                border-radius: 8px;
            }
            #StatusLabel {
                color: #A0A0A0;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #333;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            
            /* Novo Estilo de Toggle Switch */
            QCheckBox {
                color: #A0A0A0;
                font-size: 12px;
                spacing: 7px; /* Espaço entre o switch e o texto */
            }
            QCheckBox::indicator {
                /* O 'trilho' e o 'círculo' são simulados aqui */
                width: 40px;
                height: 20px;
                border-radius: 10px; /* Arredonda o trilho */
                border: 2px solid #555;
            }
            QCheckBox::indicator:unchecked {
                /* Círculo branco à esquerda, fundo cinza */
                background-color: qradialgradient(
                    cx:0.25, cy:0.5, fx:0.25, fy:0.5, radius: 0.9, 
                    stop:0 #FFFFFF, stop:1 #777777
                );
                border: 2px solid #777;
            }
            QCheckBox::indicator:checked {
                /* Círculo branco à direita, fundo verde */
                background-color: qradialgradient(
                    cx:0.75, cy:0.5, fx:0.75, fy:0.5, radius: 0.9, 
                    stop:0 #FFFFFF, stop:1 #2ECC71
                );
                border: 2px solid #2ECC71;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #999;
            }
            QCheckBox::indicator:checked:hover {
                border: 2px solid #3FEA84;
            }
        """)
        # --- FIM DA MUDANÇA ---

        self.visual_core = QLabel(self.main_frame)
        self.visual_core.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.response_label = QLabel("...", self.main_frame)
        self.response_label.setObjectName("ResponseLabel")
        self.response_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.response_label.setWordWrap(True)
        self.response_label.setMinimumHeight(100)

        self.prompt_input = QLineEdit(self.main_frame)
        self.prompt_input.setPlaceholderText("Digite um comando...")

        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Ryas: Carregando...", self.main_frame)
        self.status_label.setObjectName("StatusLabel")

        self.quick_mode_toggle = QCheckBox("Modo Rápido", self.main_frame)

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.quick_mode_toggle)

        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(15, 15, 15, 15)
        frame_layout.addWidget(self.response_label, 1)
        frame_layout.addWidget(self.visual_core, 0, Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.prompt_input)
        frame_layout.addLayout(bottom_layout)

        self.set_visual_state("idle")

    @pyqtSlot(str)
    def set_visual_state(self, state: str):
        # ... (função sem alteração)
        if state == self.current_state:
            return
        self.current_state = state
        print(f"LOG: Mudando estado visual para '{state}'")
        self.listening_movie.stop()
        self.thinking_movie.stop()
        self.speaking_movie.stop()
        if state == "idle":
            if self.idle_pixmap:
                self.visual_core.setPixmap(
                    self.idle_pixmap.scaled(
                        128, 128, Qt.AspectRatioMode.KeepAspectRatio
                    )
                )
            else:
                self.visual_core.clear()
        elif state == "listening":
            self.visual_core.setMovie(self.listening_movie)
            self.listening_movie.setScaledSize(QSize(128, 128))
            self.listening_movie.start()
        elif state == "thinking":
            self.visual_core.setMovie(self.thinking_movie)
            self.thinking_movie.setScaledSize(QSize(128, 128))
            self.thinking_movie.start()
        elif state == "speaking":
            self.visual_core.setMovie(self.speaking_movie)
            self.speaking_movie.setScaledSize(QSize(128, 128))
            self.speaking_movie.start()

    def connect_signals(self):
        # ... (função sem alteração)
        self.prompt_input.returnPressed.connect(self.on_send_text_command)
        self.ryas_core.ai_response_ready.connect(self.update_ai_response)
        self.ryas_core.status_update_ready.connect(self.update_status)
        self.ryas_core.state_changed.connect(self.set_visual_state)
        self.quick_mode_toggle.toggled.connect(self.ryas_core.set_quick_mode)

    def on_send_text_command(self):
        # ... (função sem alteração)
        user_prompt = self.prompt_input.text()
        if user_prompt:
            self.ryas_core.state_changed.emit("thinking")
            self.ryas_core.process_user_prompt(user_prompt)
            self.prompt_input.clear()

    @pyqtSlot(str)
    def update_ai_response(self, response_text):
        # ... (função sem alteração)
        self.response_label.setText(response_text)

    @pyqtSlot(str)
    def update_status(self, status_text):
        # ... (função sem alteração)
        self.status_label.setText(f"Ryas: {status_text}")

    def closeEvent(self, event: QCloseEvent):
        # ... (função sem alteração)
        event.ignore()
        self.hide()

    def mousePressEvent(self, event):
        # ... (função sem alteração)
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragPos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        # ... (função sem alteração)
        if self.dragPos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos)
            self.dragPos = event.globalPosition().toPoint()
            event.accept()
