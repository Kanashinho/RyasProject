# /main.py - VERSÃO COM FLUXO DE LOGIN

import sys
from pathlib import Path

# Adicionar QTimer e QDialog
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon

from ryas_core.main_logic import RyasCore

# --- NOVA IMPORTAÇÃO ---
# Importa a janela de login que criamos
from ryas_ui.login_dialog import LoginDialog
from ryas_ui.main_window import MainWindow

# --- LÓGICA DO ÍCONE DA BANDEJA (Inalterada) ---

# Variáveis globais para os ícones e o objeto do ícone
tray_icon = None
default_icon = None
alert_icon = None


def create_tray_icon(app: QApplication, window: MainWindow, core: RyasCore):
    global tray_icon, default_icon, alert_icon  # Permite modificar as globais

    assets_path = Path(__file__).parent / "assets"
    default_icon_path = str(assets_path / "tray_default.png")
    alert_icon_path = str(assets_path / "tray_alert.png")

    # Armazena os ícones carregados
    default_icon = QIcon(default_icon_path)
    alert_icon = QIcon(alert_icon_path)

    tray_icon = QSystemTrayIcon(default_icon, parent=app)  # Inicia com o padrão
    tray_icon.setToolTip("Ryas - Assistente Carmesim")

    menu = QMenu()

    toggle_action = QAction("Mostrar / Esconder Ryas", app)
    toggle_action.triggered.connect(lambda: toggle_window(window))
    menu.addAction(toggle_action)

    menu.addSeparator()

    quit_action = QAction("Sair", app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray_icon.setContextMenu(menu)

    tray_icon.activated.connect(
        lambda reason: toggle_window(window)
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )

    # Conecta o sinal do RyasCore à nossa nova função de atualização
    core.tray_icon_change_request.connect(update_tray_icon)

    return tray_icon


def toggle_window(window: MainWindow):
    if window.isVisible():
        window.hide()
    else:
        window.show()
        # Ao mostrar, volta para o ícone padrão (remove o alerta)
        update_tray_icon("default")


def update_tray_icon(status: str):
    global tray_icon, default_icon, alert_icon
    if tray_icon:
        if status == "alert":
            print("LOG: Mudando ícone da bandeja para ALERTA.")
            tray_icon.setIcon(alert_icon)
            # Volta ao ícone padrão após 10 segundos
            QTimer.singleShot(10000, lambda: update_tray_icon("default"))

        elif status == "default":
            if (
                tray_icon.icon().cacheKey() != default_icon.cacheKey()
            ):  # Evita mudança desnecessária
                print("LOG: Mudando ícone da bandeja para PADRÃO.")
                tray_icon.setIcon(default_icon)
        else:
            print(f"AVISO: Status de ícone desconhecido '{status}'")


# --- FIM DA LÓGICA DO ÍCONE DA BANDEJA ---


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 1. Criar o cérebro primeiro
    ryas_brain = RyasCore()

    # 2. Criar e executar o diálogo de login
    # O diálogo de login precisa do cérebro para verificar a senha
    login_dialog = LoginDialog(ryas_brain)

    # O .exec() bloqueia a execução até o usuário logar ou fechar
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        # 3. Senha Correta! Continuar a inicialização normal
        print("LOG: Autenticação bem-sucedida. Iniciando interface principal.")

        # Agora criamos a janela principal
        window = MainWindow(ryas_brain)

        # Cria o ícone da bandeja
        create_tray_icon(app, window, ryas_brain)

        # Conecta os sinais de parada
        app.aboutToQuit.connect(ryas_brain.stop)

        # Inicia as threads do cérebro (audição, fala, etc.)
        ryas_brain.start()

        # Mostra o ícone da bandeja
        if tray_icon:
            tray_icon.show()

        # Mostra a janela principal
        window.show()

        # --- DISPARAR O "OLÁ" PELA UI ---
        # (Dispara 1 segundo após a janela aparecer,
        #  dando tempo para o speaker thread estar pronto)
        # (O 'check_all_systems_ready' no main_logic.py vai chamar isso)
        def welcome_speech():
            user_callsign = ryas_brain.kb_profiles.get("user", {}).get(
                "como_chamar", "Sr. Winter"
            )
            ryas_brain.speak_this_text.emit(
                f"Olá, {user_callsign}. Autenticação bem-sucedida. Sistemas online."
            )

        # Aguarda 2 segundos para dar tempo ao Coqui TTS de carregar
        QTimer.singleShot(2000, welcome_speech)
        # --- FIM DO "OLÁ" ---

        # Inicia o loop da aplicação
        sys.exit(app.exec())

    else:
        # 4. Senha Incorreta (ou Cancelado)
        print("LOG: Falha na autenticação ou cancelado. Encerrando.")
        # Garante que o cérebro (threads) seja parado
        ryas_brain.stop()
        sys.exit()
