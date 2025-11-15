# /ryas_ui/login_dialog.py

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

# Importar o RyasCore para verificar a senha
# (Assumindo que está em ryas_core.main_logic)
from ryas_core.main_logic import RyasCore


class LoginDialog(QDialog):
    def __init__(self, ryas_brain: RyasCore, parent=None):
        super().__init__(parent)

        self.ryas_brain = ryas_brain

        self.setWindowTitle("Ryas - Autenticação Necessária")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(300)

        # --- Layout ---
        layout = QVBoxLayout()

        self.title_label = QLabel("Acesso ao Sistema Ryas")
        self.title_label.setObjectName("LoginTitle")

        self.info_label = QLabel("Por favor, insira a Senha Mestra:")
        self.info_label.setObjectName("LoginInfo")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha Mestra")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setObjectName("LoginInput")

        self.login_button = QPushButton("Autenticar")
        self.login_button.setObjectName("LoginButton")

        self.cancel_button = QPushButton("Sair")
        self.cancel_button.setObjectName("CancelButton")

        layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

        # --- Estilo (Dark Mode Básico) ---
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1d21;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 10px;
                padding: 15px;
            }
            #LoginTitle {
                font-size: 16pt;
                font-weight: bold;
                padding-bottom: 10px;
            }
            #LoginInfo {
                font-size: 10pt;
                padding-bottom: 10px;
            }
            QLineEdit {
                background-color: #2c313a;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
                color: #f0f0f0;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #007acc; /* Azul */
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 10px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #008cdd;
            }
            #CancelButton {
                background-color: #4c515a; /* Cinza */
            }
            #CancelButton:hover {
                background-color: #5c616a;
            }
        """)

        # --- Conexões ---
        self.login_button.clicked.connect(self.handle_login)
        self.cancel_button.clicked.connect(self.reject)  # Rejeita (fecha) o diálogo
        self.password_input.returnPressed.connect(self.handle_login)  # Login com Enter

    def handle_login(self):
        """
        Verifica a senha digitada com o cérebro da Ryas.
        """
        attempt = self.password_input.text()

        if self.ryas_brain.check_password(attempt):
            # Sucesso! Aceita o diálogo e fecha.
            self.accept()
        else:
            # Falha
            self.password_input.clear()
            self.info_label.setText("Senha incorreta. Tente novamente.")
            self.info_label.setStyleSheet("color: #ff4747;")  # Vermelho

            # Trava o sistema após 3 tentativas
            if self.ryas_brain.auth_attempts >= 3:
                QMessageBox.critical(
                    self,
                    "Acesso Bloqueado",
                    "Múltiplas tentativas falhas. O sistema será encerrado.",
                )
                self.reject()  # Rejeita, fazendo o main.py sair
