# /ryas_core/file_monitor.py - VERSÃO COM CONEXÃO DIRETA

import time
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from watchdog.events import FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers import Observer


# --- MUDANÇA 1: O EventHandler NÃO precisa mais ser um QObject ---
# Ele apenas chamará um método no Worker
class HoneypotEventHandler(FileSystemEventHandler):
    """
    Classe que lida com os eventos detectados pelo watchdog.
    AGORA, ele chama um método diretamente no Worker.
    """

    # Não precisa mais de __init__ ou de sinais próprios

    def __init__(self, worker_callback):
        super().__init__()
        # Armazena a função do Worker que deve ser chamada
        self.worker_callback = worker_callback
        print("DEBUG [EventHandler]: __init__ concluído.")

    def on_any_event(self, event):
        """Método chamado para QUALQUER evento."""
        if event.is_directory:
            if event.event_type not in ("moved", "deleted", "created"):
                return

        path_str = event.src_path
        event_type = event.event_type
        is_directory = event.is_directory

        if isinstance(event, FileSystemMovedEvent):
            path_str = f"{event.src_path} -> {event.dest_path}"

        print(
            f"DEBUG [EventHandler]: Evento '{event_type}' detectado em '{path_str}'. Chamando callback do Worker..."
        )
        # --- MUDANÇA 2: Chama o método do Worker diretamente ---
        # Passa os dados do evento para a função 'process_event' do Worker
        if self.worker_callback:
            self.worker_callback(event_type, path_str, is_directory)


class FileMonitorWorker(QObject):
    """
    Worker que executa o monitoramento em uma thread separada.
    """

    honeypot_alert = pyqtSignal(str, str)  # Este é o sinal que o RyasCore ouvirá
    status_update = pyqtSignal(str)

    def __init__(self, paths_to_watch):
        super().__init__()
        print("DEBUG [Worker]: __init__ iniciado.")
        self.paths_to_watch = [Path(p) for p in paths_to_watch if Path(p).exists()]
        if not self.paths_to_watch:
            print("AVISO [Worker]: Nenhum caminho válido para monitorar.")

        self.observer = None
        # --- MUDANÇA 3: Passa o método 'self.process_event' para o handler ---
        # Agora o handler tem uma referência direta para chamar nossa função
        self.event_handler = HoneypotEventHandler(worker_callback=self.process_event)

        # A conexão interna foi REMOVIDA
        print("DEBUG [Worker]: __init__ concluído.")

    def start_monitoring(self):
        # ... (código sem alteração, continua agendando self.event_handler) ...
        if not self.paths_to_watch:
            self.status_update.emit("Monitoramento inativo (sem alvos).")
            return
        self.observer = Observer()
        monitored_targets_str = []
        for path in self.paths_to_watch:
            try:
                self.observer.schedule(self.event_handler, str(path), recursive=True)
                monitored_targets_str.append(f"'{path.name}'")
                print(f"LOG [FileMonitor]: Monitorando '{path}' recursivamente.")
            except Exception as e:
                print(
                    f"ERRO [FileMonitor]: Falha ao agendar monitoramento para '{path}': {e}"
                )
        if not self.observer.emitters:
            self.status_update.emit("Monitoramento falhou (nenhum alvo agendado).")
            return
        try:
            self.observer.start()
            targets_list_str = ", ".join(monitored_targets_str)
            self.status_update.emit(
                f"Monitorando {len(monitored_targets_str)} alvos: {targets_list_str}"
            )
            print("LOG [FileMonitor]: Observer iniciado.")
            while self.observer.is_alive():
                time.sleep(1)
        except Exception as e:
            print(f"ERRO CRÍTICO [FileMonitor]: Falha ao iniciar observer: {e}")
            self.status_update.emit("Erro crítico no monitoramento.")
        finally:
            if self.observer and self.observer.is_alive():
                self.observer.stop()
            if self.observer:
                self.observer.join()
            print("LOG [FileMonitor]: Observer finalizado.")

    def stop_monitoring(self):
        # ... (código sem alteração) ...
        if self.observer and self.observer.is_alive():
            print("LOG [FileMonitor]: Parando observer...")
            self.observer.stop()

    # --- MUDANÇA 4: 'process_event' NÃO é mais um @pyqtSlot ---
    # É apenas um método normal chamado diretamente pelo EventHandler
    def process_event(self, event_type, path_str, is_directory):
        """Processa o evento bruto e emite o sinal de alerta formatado."""
        print(
            f"DEBUG [Worker]: Método process_event foi CHAMADO com: {event_type}, {path_str}"
        )

        alert_message = f"Alerta! Acesso '{event_type}' detectado em: {path_str}"
        print(f"DEBUG [Worker]: Emitindo sinal honeypot_alert...")
        # Este sinal (honeypot_alert) é o que o RyasCore está conectado
        self.honeypot_alert.emit(event_type, path_str)
        print(f"LOG [FileMonitor]: ALERTA EMITIDO - {alert_message}")


# --- Função de Teste (Opcional, sem alteração) ---
# ... (código de teste) ...

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication
    # test_monitor()
