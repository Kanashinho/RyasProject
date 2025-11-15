# /ryas_core/main_logic.py - VERSÃO: FASE 6.2 (Gerenciamento de Honeypot por Voz) + Lógica de Senha + CORREÇÃO DE NOTÍCIAS

import configparser
import json
import re  # Importar regex para futuras extrações (como URL/Hash)
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

# Importações dos Módulos
from .ai_abstraction import AIAbstractionLayer
from .audio_utils import listen_and_transcribe
from .file_monitor import FileMonitorWorker
from .hardware_monitor import get_alert_status, get_cpu_temperatures, get_system_vitals
from .network_tools import scan_local_network
from .ntfy_manager import send_notification
from .payload_manager import PayloadManager
from .speech_synthesis import Speaker
from .system_utils import detect_hardware_profile
from .transcriber import TranscriberWorker
from .virus_total_analyzer import (  # Importações do VT
    analyze_file_by_path,
    analyze_hash,
    analyze_url,
)
from .wake_word_detector import WakeWordDetector

try:
    from .web_tools import fetch_filtered_news
except ImportError as e:
    print(
        f"AVISO: Falha ao importar 'web_tools': {e}. Briefing de notícias desabilitado."
    )
    fetch_filtered_news = None


class RyasCore(QObject):
    # --- Sinais ---
    ai_response_ready = pyqtSignal(str)
    status_update_ready = pyqtSignal(str)
    speak_this_text = pyqtSignal(str)
    speech_about_to_start = pyqtSignal()
    state_changed = pyqtSignal(str)
    honeypot_alert_signal = pyqtSignal(str, str)
    tray_icon_change_request = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        print("LOG: Cérebro da Ryas (RyasCore) inicializado.")

        # --- Estado Interno ---
        self.kb_profiles = {}
        self.kb_system = {}
        self.system_prompt_template = (
            "Ryas: Erro ao carregar KB. Usuário: {prompt}"  # Fallback
        )
        self.quick_mode_enabled = False
        self.is_collecting_payload_data = False
        self.payload_creation_step = 0
        self.new_payload_data = {}
        self.transcriber_ready = False
        self.speaker_ready = False

        # --- ESTADO: MACs Conhecidos ---
        self.known_macs = set()

        # --- NOVO ESTADO: Autenticação ---
        self.is_authenticated = False
        self.master_password = ""
        self.auth_attempts = 0  # Contador para limitar tentativas

        # --- Módulos Principais ---
        self.ai = AIAbstractionLayer()
        # Passamos a IA para o PayloadManager
        self.payload_manager = PayloadManager(self.ai)

        # --- TIMERS ---
        self.briefing_timer = QTimer(self)
        self.briefing_timer.timeout.connect(self._send_daily_briefing)
        self.network_scan_timer = QTimer(self)
        self.network_scan_timer.timeout.connect(self._run_proactive_scan)

        # --- Módulos em Threads ---
        self.transcriber_thread = None
        self.transcriber = None
        self.speaker_thread = None
        self.speaker = None
        self.wake_word_detector = None
        self.monitor_thread = None
        self.monitor_worker = None

        # --- Configuração ---
        self.chat_model = None
        self.code_model = None

        # --- Inicialização ---
        self._load_knowledge_base()
        self.setup_transcriber()
        self.setup_speaker()
        self.load_config()  # Carrega modelos de IA, chaves E SENHA
        self.setup_file_monitor()

    def _load_knowledge_base(self):
        """Carrega os arquivos JSON, constrói o prompt e carrega os MACs conhecidos."""
        base_dir = Path(__file__).parent.parent
        self.kb_path = base_dir / "knowledge_base"
        print(f"LOG: Procurando Base de Conhecimento em: {self.kb_path}")

        try:
            with open(self.kb_path / "kb_profiles.json", "r", encoding="utf-8") as f:
                self.kb_profiles = json.load(f)
            with open(self.kb_path / "kb_system.json", "r", encoding="utf-8") as f:
                self.kb_system = json.load(f)
            print("LOG: Base de Conhecimento (KB) carregada com sucesso.")

            # --- CARREGAR MACs CONHECIDOS ---
            known_macs_list = self.kb_system.get("rede_confiavel", {}).get(
                "macs_conhecidos", []
            )
            self.known_macs = set([mac.upper() for mac in known_macs_list])
            print(
                f"LOG: Inventário de MACs: {len(self.known_macs)} dispositivos conhecidos."
            )

        except FileNotFoundError:
            print(
                f"ERRO CRÍTICO: Arquivos de Base de Conhecimento não encontrados em {self.kb_path}."
            )
            self.kb_profiles = {}
            self.kb_system = {}
            return
        except json.JSONDecodeError as e:
            print(
                f"ERRO CRÍTICO: Falha ao decodificar JSON em {self.kb_path}. Detalhes: {e}"
            )
            self.kb_profiles = {}
            self.kb_system = {}
            return
        except Exception as e:
            print(f"ERRO ao carregar Base de Conhecimento: {e}")
            return

        # ... (Construção do system_prompt_template) ...
        try:
            user_info = self.kb_profiles.get("user", {})
            ryas_info = self.kb_profiles.get("ryas", {})
            personality_rules = ryas_info.get("personalidade", {})
            user_callsign = user_info.get("como_chamar", "Usuário")

            diretrizes_comportamento = [
                f"1.  **Missão:** {ryas_info.get('missao', 'Ser uma assistente.')}",
                f'2.  **Seu Criador/Usuário:** Chame-o de "{user_callsign}". NUNCA use outro nome.',
                f"3.  **Idioma Mandatório:** Responda **SEMPRE e SOMENTE** em Português do Brasil. NUNCA use inglês.",
            ]
            rule_number = 4
            for key, value in personality_rules.items():
                diretrizes_comportamento.append(
                    f"{rule_number}.  **{key.replace('_', ' ').capitalize()}:** {value}"
                )
                rule_number += 1
            diretrizes_comportamento.append(
                f'{rule_number}.  **Regra de Contexto:** Use **ESTRITAMENTE e APENAS** as informações da "SUA MEMÓRIA". NUNCA invente.'
            )
            diretrizes_str = "\n".join(diretrizes_comportamento)

            contexto_profiles_str = json.dumps(
                self.kb_profiles, indent=2, ensure_ascii=False
            )
            contexto_system_str = json.dumps(
                self.kb_system, indent=2, ensure_ascii=False
            )
            contexto_profiles_escaped = contexto_profiles_str.replace(
                "{", "{{"
            ).replace("}", "}}")
            contexto_system_escaped = contexto_system_str.replace("{", "{{").replace(
                "}", "}}"
            )

            self.system_prompt_template = f"""Você é Ryas ({ryas_info.get("nome_completo", "Ryas")}). Siga **TODAS** as diretrizes abaixo **SEM EXCEÇÃO**.
### SUA MEMÓRIA (Use esta informação para responder) ###
{contexto_profiles_escaped}
{contexto_system_escaped}
### FIM DA MEMÓRIA ###
### DIRETRIZES DE COMPORTAMENTO OBRIGATÓRIAS ###
{diretrizes_str}
Usuário: {{prompt}}
Ryas:"""
            self.system_prompt_template = self.system_prompt_template.replace(
                "{{prompt}}", "{prompt}"
            )
            print("LOG: Prompt de Sistema construído dinamicamente a partir da KB.")

        except Exception as e:
            print(f"ERRO CRÍTICO ao construir prompt da KB: {e}")

    def _save_known_macs(self):
        """Salva a lista atualizada de MACs conhecidos de volta para o kb_system.json."""
        if not self.kb_system:
            print("ERRO: Não foi possível salvar MACs, KB não carregada.")
            return

        try:
            if "rede_confiavel" not in self.kb_system:
                self.kb_system["rede_confiavel"] = {}

            self.kb_system["rede_confiavel"]["macs_conhecidos"] = sorted(
                list(self.known_macs)
            )

            with open(self.kb_path / "kb_system.json", "w", encoding="utf-8") as f:
                json.dump(self.kb_system, f, indent=2, ensure_ascii=False)

            print(f"LOG: Inventário de MACs (KB) salvo. Total: {len(self.known_macs)}.")

        except Exception as e:
            print(f"ERRO: Falha ao salvar MACs para KB: {e}")

    @pyqtSlot(bool)
    def set_quick_mode(self, enabled):
        """Controla se a síntese de voz deve ser pulada."""
        self.quick_mode_enabled = enabled
        status = "ATIVADO" if enabled else "DESATIVADO"
        print(f"LOG: Modo Rápido (Texto-Apenas) {status}.")

    def setup_file_monitor(self):
        """Configura e inicia o monitoramento de arquivos (Honeypot)."""
        config_path = Path(__file__).parent.parent / "config.ini"

        if self.monitor_worker:
            self.monitor_worker.stop_monitoring()
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.quit()
            self.monitor_thread.wait()

        config = configparser.ConfigParser()
        paths_to_watch_str = ""

        try:
            if config_path.is_file():
                config.read(config_path)
                paths_to_watch_str = config.get(
                    "HONEYPOT", "paths_to_watch", fallback=""
                )
            else:
                print("AVISO [FileMonitor]: config.ini não encontrado.")

        except (configparser.NoSectionError, configparser.NoOptionError):
            print("AVISO [FileMonitor]: Seção [HONEYPOT] não encontrada.")
        except Exception as e:
            print(f"ERRO [FileMonitor]: Falha ao ler config: {e}")

        paths_list = [p.strip() for p in paths_to_watch_str.split(",") if p.strip()]

        if not paths_list:
            print("LOG [FileMonitor]: Nenhum caminho configurado.")
            self.monitor_worker = None
            self.monitor_thread = None
            return

        print(f"LOG [FileMonitor]: Configurado para monitorar: {paths_list}")

        self.monitor_thread = QThread()
        self.monitor_worker = FileMonitorWorker(paths_list)
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_worker.honeypot_alert.connect(self.on_honeypot_alert)
        self.monitor_worker.status_update.connect(self.status_update_ready)
        self.monitor_thread.started.connect(self.monitor_worker.start_monitoring)
        self.monitor_thread.start()

    def _update_honeypot_config(self, new_paths: list):
        """
        Atualiza o config.ini com a nova lista de paths e reinicia o monitor.
        """
        config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent / "config.ini"

        if config_path.is_file():
            config.read(config_path)

        if "HONEYPOT" not in config:
            config["HONEYPOT"] = {}

        config["HONEYPOT"]["paths_to_watch"] = ", ".join(new_paths)

        try:
            with open(config_path, "w") as configfile:
                config.write(configfile)
            print(f"LOG: config.ini do Honeypot salvo com {len(new_paths)} caminhos.")

            self.setup_file_monitor()
            return True

        except Exception as e:
            print(f"ERRO: Falha ao salvar ou reiniciar Honeypot: {e}")
            return False

    def _get_current_honeypot_paths(self, raw=False, numbered=False):
        """Retorna a lista de caminhos do Honeypot do config.ini."""
        config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent / "config.ini"

        if config_path.is_file():
            config.read(config_path)

        paths_str = config.get("HONEYPOT", "paths_to_watch", fallback="")
        paths_list = [p.strip() for p in paths_str.split(",") if p.strip()]

        if raw:
            return paths_list

        if numbered:
            return "\n" + "\n".join(
                [f"  {i + 1}. {Path(p).name}" for i, p in enumerate(paths_list)]
            )

        if not paths_list:
            return "NENHUM caminho configurado."

        return ", ".join([Path(p).name for p in paths_list])

    @pyqtSlot(str, str)
    def on_honeypot_alert(self, event_type, path_str):
        """Chamado quando o FileMonitorWorker detecta um evento."""
        file_name = Path(path_str).name
        alert_text = f"ALERTA: {event_type} em {file_name}"
        log_message = f"ALERTA HONEYPOT! Evento '{event_type}' em: {path_str}"
        print(f"LOG: {log_message}")

        self.honeypot_alert_signal.emit(event_type, path_str)
        self.status_update_ready.emit(alert_text)
        self.tray_icon_change_request.emit("alert")

        # --- INTEGRAÇÃO VIRUSTOTAL (Fase 6.4) ---
        self.status_update_ready.emit(f"Analisando '{file_name}' no VirusTotal...")

        vt_result = analyze_file_by_path(path_str)

        if vt_result["status"] == "sucesso":
            malicious_count = vt_result["malicious"]

            if malicious_count > 0:
                message = f"ATENÇÃO! {file_name} foi detectado como MALICIOSO por {malicious_count} fornecedor(es)."
                self.notify_user(
                    title="Ryas 🚨 MALWARE DETECTADO!",
                    message=message,
                    tags="skull",
                    priority="max",
                    speak_message=True,
                )
            else:
                message = f"{file_name} analisado. {vt_result['reputation']} fornecedores detectaram ameaça. Status: Limpo."
                self.notify_user(
                    title="Ryas 🟢 Alerta Analisado",
                    message=message,
                    tags="shield",
                    priority="default",
                )
            self.status_update_ready.emit(f"Análise VT: {vt_result['reputation']}")

        elif vt_result["status"] == "nao_analisado":
            message = f"Evento '{event_type}' detectado no arquivo: {file_name}. (Novo, não verificado no VT)"
            self.notify_user(
                title="Ryas 🟡 Alerta Honeypot", message=message, tags="warning"
            )

        else:
            message = f"Falha na análise do VirusTotal: {vt_result['message']}"
            self.notify_user(title="Ryas ❌ Erro de API", message=message, tags="bug")

    def setup_transcriber(self):
        """Configura e inicia o worker de transcrição."""
        self.transcriber_thread = QThread()
        self.transcriber = TranscriberWorker(model_size="medium")
        self.transcriber.moveToThread(self.transcriber_thread)
        self.transcriber_thread.started.connect(self.transcriber.load_model)
        self.transcriber.transcription_ready.connect(self.on_transcription_finished)
        self.transcriber.status_update.connect(self.status_update_ready)
        self.transcriber.model_loaded.connect(self.on_transcriber_ready)
        self.transcriber_thread.start()

    def setup_speaker(self):
        """Configura e inicia o worker de síntese de voz."""
        self.speaker_thread = QThread()
        self.speaker = Speaker()
        self.speaker.moveToThread(self.speaker_thread)
        self.speaker_thread.started.connect(self.speaker.load_voice_model)
        self.speak_this_text.connect(self.speaker.say)
        self.speaker.model_loaded.connect(self.on_speaker_ready)
        self.speaker.speech_started.connect(lambda: self.state_changed.emit("speaking"))
        self.speaker.speech_finished.connect(
            lambda: (
                self.status_update_ready.emit("Pronta."),
                self.state_changed.emit("idle"),
            )
        )
        self.speaker_thread.start()

    def on_transcriber_ready(self):
        self.transcriber_ready = True
        print("LOG: Módulo de Transcrição PRONTO.")
        self.check_all_systems_ready()

    def on_speaker_ready(self):
        self.speaker_ready = True
        print("LOG: Módulo de Fala PRONTO.")
        self.check_all_systems_ready()

    def check_all_systems_ready(self):
        """Verifica se todos os módulos essenciais estão prontos e ativa os Timers."""
        if self.transcriber_ready and self.speaker_ready:
            print("LOG: Todos os sistemas de IA estão prontos. Ativando 'wake word'.")
            self.state_changed.emit("idle")

            # --- MENSAGEM DE OLÁ ---
            # Removida daqui. Será chamada pelo main.py APÓS o login.

            if self.wake_word_detector:
                self.wake_word_detector.start()
            else:
                print(
                    "AVISO: Wake Word não inicializado. Ativação por voz desabilitada."
                )

            # --- INICIAR TIMER DE SCAN DE REDE (1 hora - Byakugan Proativo) ---
            print("LOG: Configurando Byakugan Proativo (Scan de Rede) a cada 1 hora.")
            one_hour_ms = 60 * 60 * 1000
            self.network_scan_timer.start(one_hour_ms)
            QTimer.singleShot(5000, self._run_proactive_scan_initial)
            # --- FIM DO TIMER ---

            # --- INICIAR TIMER DE NOTÍCIAS ---
            if fetch_filtered_news is not None:
                print("LOG: Configurando briefing diário de notícias.")
                twenty_four_hours_ms = 24 * 60 * 60 * 1000
                self.briefing_timer.start(twenty_four_hours_ms)
            else:
                print("LOG: Módulo de notícias não encontrado, briefing desabilitado.")
            # --- FIM DO TIMER ---

    def load_config(self):
        """Carrega configurações gerais, modelos de IA, chaves e SENHA."""
        config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent / "config.ini"
        if not config_path.is_file():
            print(f"ERRO CRÍTICO: '{config_path}' não encontrado.")
            return
        config.read(config_path)

        # Carregar Modelos de IA
        profile_key = detect_hardware_profile()
        profile_section = f"AI_MODEL_{profile_key.upper()}"
        if not config.has_section(profile_section):
            default_profile = config.get(
                "Profiles", "default_profile", fallback="notebook"
            )
            profile_section = f"AI_MODEL_{default_profile.upper()}"
        print(f"LOG: Perfil: '{profile_key}'")
        self.chat_model = config.get(profile_section, "chat_model")
        self.code_model = config.get(profile_section, "code_model")
        print(f"LOG: Chat: '{self.chat_model}'")
        print(f"LOG: Código: '{self.code_model}'")

        # Carregar Picovoice
        try:
            picovoice_key = config.get("Picovoice", "access_key")
            keyword_filename = config.get("Picovoice", "model_path")
            lang_model_filename = config.get("Picovoice", "language_model_path")
            keyword_path = Path(__file__).parent.parent / keyword_filename
            lang_model_path = Path(__file__).parent.parent / lang_model_filename
            if not keyword_path.is_file():
                print(
                    f"ERRO: Arquivo de keyword Picovoice não encontrado em {keyword_path}"
                )
                raise FileNotFoundError()
            self.wake_word_detector = WakeWordDetector(
                access_key=picovoice_key,
                keyword_path=str(keyword_path),
                model_path=str(lang_model_path) if lang_model_path.is_file() else None,
            )
            self.wake_word_detector.wake_word_detected.connect(
                self.activate_voice_input
            )
            print("LOG: Detector de Wake Word (Picovoice) inicializado.")
        except FileNotFoundError:
            pass
        except (configparser.NoSectionError, configparser.NoOptionError):
            print("AVISO: Seção [Picovoice] ou chaves não encontradas no config.ini.")
        except Exception as e:
            print(f"ERRO ao inicializar o WakeWordDetector: {e}")

        # --- CARREGAR SENHA MESTRE ---
        try:
            self.master_password = config.get(
                "SECURITY", "MASTER_PASSWORD", fallback=""
            ).strip()
            if not self.master_password:
                print(
                    "AVISO: Senha Mestra não configurada em [SECURITY]. Desativando autenticação."
                )
                self.is_authenticated = (
                    True  # Desativa a autenticação se não houver senha.
                )
            else:
                print("LOG: Senha Mestra carregada. Autenticação será necessária.")
        except Exception as e:
            print(f"ERRO ao carregar Senha Mestra: {e}")
            self.is_authenticated = True  # Falha segura (desativa auth)

    def start(self):
        """Chamado quando a aplicação inicia."""
        print("LOG: RyasCore iniciado. Aguardando módulos...")
        self.state_changed.emit("thinking")

    def stop(self):
        """Chamado quando a aplicação está fechando."""
        print("LOG: RyasCore encerrando...")
        if self.briefing_timer:
            self.briefing_timer.stop()
        if self.network_scan_timer:
            self.network_scan_timer.stop()

        if self.monitor_worker:
            self.monitor_worker.stop_monitoring()
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.quit()
            self.monitor_thread.wait()

        if self.transcriber_thread:
            self.transcriber_thread.quit()
            self.transcriber_thread.wait()
            print("LOG: Transcriber thread finalizada.")
        if self.speaker_thread:
            self.speaker_thread.quit()
            self.speaker_thread.wait()
            print("LOG: Speaker thread finalizada.")
        if self.wake_word_detector:
            self.wake_word_detector.stop()
            print("LOG: Wake Word detector parado.")
        print("LOG: RyasCore encerrado.")

    def notify_user(
        self,
        title: str,
        message: str,
        priority: str = "high",
        tags: str = None,
        speak_message: bool = False,
    ):
        """
        Envia uma notificação push para o usuário e, opcionalmente, fala a mensagem.
        """
        print(f"LOG: Enviando notificação para o usuário: {title}")

        send_notification(title, message, priority, tags)

        if speak_message:
            self.speak_this_text.emit(f"Alerta, Mestre. {message}")

    # --- NOVO MÉTODO DE AUTENTICAÇÃO ---
    def check_password(self, attempt: str) -> bool:
        """
        Verifica a senha digitada contra a senha mestra carregada.
        """
        if self.is_authenticated:  # Se já estiver logado
            return True

        if attempt.strip() == self.master_password:
            self.is_authenticated = True
            self.auth_attempts = 0
            print("LOG: Autenticação bem-sucedida.")
            return True
        else:
            self.auth_attempts += 1
            print(f"ERRO: Tentativa de login falhou (Tentativa {self.auth_attempts})")
            if self.auth_attempts >= 3:
                print("ALERTA: 3 tentativas de login falhas. Notificando usuário.")
                self.notify_user(
                    title="Ryas 🚨 ALERTA DE SEGURANÇA",
                    message="Múltiplas tentativas de login falhas foram detectadas na sua instância da Ryas.",
                    priority="max",
                    tags="lock",
                )
            return False

    @pyqtSlot()
    def _send_daily_briefing(self):
        """
        Busca as notícias do dia e as envia para o usuário via ntfy.
        """
        print("LOG: [Timer Event] Executando briefing diário de notícias...")
        if fetch_filtered_news is None:
            print("LOG: [Briefing] Falha: Módulo 'web_tools' não carregado.")
            return

        user_interests = self.kb_profiles.get("user", {}).get("interesses", [])
        user_callsign = self.kb_profiles.get("user", {}).get(
            "como_chamar", "Sr. Winter"
        )

        try:
            news_results = fetch_filtered_news(user_interests)
        except Exception as e:
            print(f"ERRO: [Briefing] Falha ao buscar notícias: {e}")
            self.notify_user(
                title="Ryas 🟡 Erro no Briefing",
                message=f"Não consegui buscar suas notícias. Detalhe: {e}",
                tags="warning",
            )
            return

        if isinstance(news_results, str):
            print(f"LOG: [Briefing] Erro retornado por web_tools: {news_results}")
            self.notify_user(
                title="Ryas 🟡 Erro no Briefing", message=news_results, tags="warning"
            )

        elif isinstance(news_results, list) and news_results:
            num_news = len(news_results)
            title = f"Ryas 📰 Seu Briefing de Notícias ({num_news})"

            # --- INÍCIO DA CORREÇÃO (Tradução via IA) ---
            # Formata os títulos para a IA
            formatted_news = "\n".join(
                [f"{i + 1}. {item['title']}" for i, item in enumerate(news_results[:5])]
            )

            # Constrói um prompt robusto exigindo português
            briefing_prompt = f"""Ryas, prepare um resumo curto (apenas a lista de títulos) para o briefing diário do {user_callsign}.
**REGRA OBRIGATÓRIA:** Responda **SEMPRE e SOMENTE** em Português do Brasil. Se os títulos estiverem em inglês, TRADUZA-OS.
**FORMATO:** Apenas a lista numerada.

Títulos:
{formatted_news}
"""

            # Chama a IA para processar (traduzir) os títulos
            message_body = self.ai.generate_text(self.chat_model, briefing_prompt)

            # Limpa a resposta da IA (remove saudações, ex: "Claro, Mestre...")
            if "1." in message_body:
                message_body = message_body[message_body.find("1.") :]

            print(
                f"LOG: [Briefing] Enviando {num_news} notícias (processadas por IA) para o usuário."
            )
            self.notify_user(title=title, message=message_body, tags="newspaper")
            # --- FIM DA CORREÇÃO ---

        else:
            print("LOG: [Briefing] Sem notícias de interesse encontradas hoje.")

    @pyqtSlot()
    def _run_proactive_scan_initial(self):
        """Dispara o scan inicial que cria o inventário se ele estiver vazio."""
        if not self.known_macs:
            print(
                "LOG: [Byakugan] Inventário vazio. Iniciando Scan para APRENDIZADO..."
            )
            self.status_update_ready.emit("Byakugan: Construindo Inventário de Rede...")
            self._run_proactive_scan(is_learning_mode=True)
            self.status_update_ready.emit("Pronta.")
        else:
            print("LOG: [Byakugan] Inventário existente. Aguardando timer de 1h.")

    @pyqtSlot()
    def _run_proactive_scan(self, is_learning_mode=False):
        """
        Executa o scan de rede e verifica novos dispositivos (Intrusos).
        """
        print(
            f"LOG: [Timer Event] Executando Scan Proativo (Inventário={len(self.known_macs)})."
        )

        scan_results = scan_local_network()

        if isinstance(scan_results, str):
            self.notify_user(
                title="Ryas 🟡 Erro no Byakugan",
                message=f"Falha no Scan de Rede: {scan_results}",
                tags="warning",
            )
            return

        newly_discovered_macs = set()

        for device in scan_results:
            mac = device.get("mac", "").upper()
            if mac and mac not in self.known_macs:
                newly_discovered_macs.add(mac)

        # --- LÓGICA DE ALERTA/APRENDIZADO ---
        if newly_discovered_macs:
            if is_learning_mode:
                # Modo Aprendizado (Primeira execução)
                self.known_macs.update(newly_discovered_macs)
                self._save_known_macs()
                print(
                    f"LOG: [Byakugan] Adicionados {len(newly_discovered_macs)} novos MACs ao Inventário (Total: {len(self.known_macs)})."
                )

            else:
                # Modo Alerta (Intrusão)
                macs_list = "\n".join(newly_discovered_macs)
                alert_message = f"Ryas detectou {len(newly_discovered_macs)} novo(s) dispositivo(s) não catalogado(s) na rede:\n{macs_list}\n\nSe confiável, reinicie Ryas para incluir no inventário."

                print(f"ALERTA CRÍTICO: Dispositivo(s) Intrusionado(s) detectado(s).")
                self.notify_user(
                    title="Ryas 🚨 INTRUSÃO DE REDE DETECTADA",
                    message=alert_message,
                    priority="max",
                    tags="rotating_light",
                    speak_message=True,
                )
                self.tray_icon_change_request.emit("alert")

        else:
            print("LOG: [Byakugan] Nenhum novo dispositivo detectado. Rede segura.")

    def activate_voice_input(self):
        """Chamado quando o Wake Word é detectado."""
        if not self.is_authenticated:
            print("LOG: Wake Word detectado, mas sistema não autenticado. Ignorando.")
            # Opcional: Tocar um som de "bloqueado"
            return

        if self.is_collecting_payload_data:
            print(
                "LOG: Wake Word detectado durante coleta de dados. Ignorando ativação de escuta."
            )
            return  # Evita interromper a coleta

        self.state_changed.emit("listening")
        audio_data = listen_and_transcribe()
        if audio_data:
            self.state_changed.emit("thinking")
            self.transcriber.transcribe_audio(audio_data)
        else:
            self.state_changed.emit("idle")

    def on_transcription_finished(self, text):
        """Chamado quando a transcrição está pronta."""
        print(f"LOG: Texto transcrito (Voz): '{text}'")
        if text or self.is_collecting_payload_data:
            self.state_changed.emit("thinking")
            self.process_user_prompt(text)
        else:
            self.status_update_ready.emit("Não entendi. Tente novamente.")
            self.state_changed.emit("idle")

    def process_user_prompt(self, prompt):
        """Roteador de Intenções Principal."""
        prompt_lower = prompt.lower().strip() if prompt else ""
        user_callsign = self.kb_profiles.get("user", {}).get(
            "como_chamar", "Sr. Winter"
        )

        final_response_text = ""
        model_to_use = self.chat_model
        intent_processed = False

        # --- LÓGICA DE COLETA DE DADOS (Payload / Honeypot - PRIORIDADE MÁXIMA) ---
        if self.is_collecting_payload_data:
            intent_processed = True

            # PASSO 6: Adicionar Monitor
            if self.payload_creation_step == 6:
                path_to_add = Path(prompt.strip())

                if not path_to_add.is_dir():
                    final_response_text = f"O caminho '{path_to_add}' não é uma pasta válida. Por favor, tente novamente."
                else:
                    current_paths = [
                        Path(p) for p in self._get_current_honeypot_paths(raw=True)
                    ]
                    if str(path_to_add) in [str(p) for p in current_paths]:
                        final_response_text = (
                            f"O caminho '{path_to_add.name}' já está sendo monitorado."
                        )
                    else:
                        current_paths.append(path_to_add)
                        if self._update_honeypot_config(
                            [str(p) for p in current_paths]
                        ):
                            final_response_text = f"Caminho '{path_to_add.name}' adicionado com sucesso. Monitoramento reiniciado."
                            self.is_collecting_payload_data = False
                        else:
                            final_response_text = (
                                "ERRO: Falha ao salvar a configuração do Honeypot."
                            )

            # PASSO 7: Remover Monitor
            elif self.payload_creation_step == 7:
                path_to_remove = prompt.strip()
                current_paths_raw = self._get_current_honeypot_paths(raw=True)

                if path_to_remove not in current_paths_raw:
                    final_response_text = f"Não encontrei o caminho '{path_to_remove}' nos caminhos monitorados. Tente novamente ou diga 'cancelar'."
                else:
                    new_paths = [p for p in current_paths_raw if p != path_to_remove]

                    if self._update_honeypot_config(new_paths):
                        final_response_text = f"Caminho '{Path(path_to_remove).name}' removido com sucesso. Monitoramento reiniciado."
                        self.is_collecting_payload_data = False
                    else:
                        final_response_text = (
                            "ERRO: Falha ao salvar a configuração do Honeypot."
                        )

            # --- Lógica de 5 passos do Payload ---
            elif self.payload_creation_step == 1:
                if not prompt:
                    final_response_text = f"{user_callsign}, repita o nome do arquivo."
                elif "." not in prompt or " " in prompt:
                    final_response_text = f"{user_callsign}, nome de arquivo inválido."
                else:
                    self.new_payload_data["filename"] = prompt
                    self.payload_creation_step = 2
                    final_response_text = (
                        f"Ok, '{prompt}'. Linguagem (python, powershell, bat)?"
                    )
            elif self.payload_creation_step == 2:
                if not prompt_lower or prompt_lower not in [
                    "python",
                    "powershell",
                    "bat",
                    "bash",
                    "sh",
                ]:
                    final_response_text = f"Linguagem inválida."
                else:
                    self.new_payload_data["language"] = prompt_lower
                    self.payload_creation_step = 3
                    final_response_text = f"'{prompt_lower}'. Descreva o payload."
            elif self.payload_creation_step == 3:
                if not prompt:
                    final_response_text = f"Não ouvi a descrição."
                else:
                    self.new_payload_data["description"] = prompt
                    self.payload_creation_step = 4
                    final_response_text = f"Ok. OS alvo (windows, linux, macos, any)?"
            elif self.payload_creation_step == 4:
                if not prompt_lower or prompt_lower not in [
                    "windows",
                    "linux",
                    "macos",
                    "any",
                    "todos",
                ]:
                    final_response_text = f"Sistema inválido."
                else:
                    self.new_payload_data["target_os"] = (
                        [prompt_lower]
                        if prompt_lower != "todos"
                        else ["windows", "linux", "macos"]
                    )
                    self.payload_creation_step = 5
                    final_response_text = (
                        f"Alvo '{prompt_lower}'. Requer admin (sim/não)?"
                    )
            elif self.payload_creation_step == 5:
                if prompt_lower not in ["sim", "não", "nao"]:
                    final_response_text = f"Responda 'sim' ou 'não'."
                else:
                    self.new_payload_data["requires_admin"] = prompt_lower == "sim"

                    self.status_update_ready.emit("Gerando script de Payload com IA...")
                    payload_name = self.new_payload_data.pop("internal_name")

                    script_result = self.payload_manager.generate_and_save_script(
                        payload_name, self.new_payload_data, self.code_model
                    )

                    if script_result.startswith("ERRO:"):
                        final_response_text = f"ERRO CRÍTICO na geração do Payload '{payload_name}'. Detalhes: {script_result}"
                    else:
                        if self.payload_manager.add_payload(
                            payload_name, self.new_payload_data
                        ):
                            final_response_text = f"Perfeito, {user_callsign}. Payload '{payload_name}' criado e código salvo como '{script_result}'."
                        else:
                            final_response_text = (
                                f"Erro ao salvar o manifesto de '{payload_name}'."
                            )

                    self.is_collecting_payload_data = False
                    self.payload_creation_step = 0
                    self.new_payload_data = {}

            if final_response_text:
                self.ai_response_ready.emit(final_response_text)

        # --- VERIFICA OUTRAS INTENÇÕES (se não estiver coletando) ---
        if not intent_processed:
            # Palavras-chave
            network_keywords = [
                "escanear",
                "scan",
                "rede",
                "byakugan",
                "escaner",
                "escaneie",
            ]
            code_keywords = [
                "código",
                "função",
                "script",
                "classe",
                "programa",
                "desenvolva",
                "python",
                "javascript",
            ]
            payload_list_keywords = [
                "liste",
                "listar",
                "quais",
                "mostre",
                "ver",
                "payloads",
                "scripts",
            ]
            payload_details_keywords = [
                "detalhes",
                "informações",
                "info",
                "sobre",
                "especifique",
                "payload",
                "script",
            ]
            payload_delete_keywords = [
                "delete",
                "deletar",
                "remover",
                "apagar",
                "payload",
                "script",
            ]
            payload_create_keywords = ["crie", "criar", "novo", "payload", "script"]
            news_keywords = ["notícias", "noticia", "novidades", "atualidades", "hoje"]

            # VirusTotal Keywords
            check_url_keywords = [
                "verificar site",
                "url é segura",
                "segurança do site",
                "site é seguro",
            ]
            check_hash_keywords = [
                "verificar hash",
                "analisar arquivo",
                "hash malicioso",
            ]

            # Honeypot Keywords
            add_monitor_keywords = ["monitorar", "adicionar", "vigiar", "novo caminho"]
            remove_monitor_keywords = [
                "remover",
                "deletar",
                "parar de vigiar",
                "remover monitor",
            ]
            list_monitor_keywords = ["listar", "quais caminhos", "mostrar monitores"]

            # --- INTENÇÃO: ANALISAR URL (VirusTotal) ---
            if any(k in prompt_lower for k in check_url_keywords):
                print("LOG: Intenção detectada: Analisar URL.")
                intent_processed = True

                url_match = re.search(r"(https?://\S+)", prompt)

                if not url_match:
                    final_response_text = f"Por favor, {user_callsign}, diga a URL completa que você deseja verificar."
                else:
                    url = url_match.group(1)
                    self.status_update_ready.emit(f"Analisando URL: {url}...")

                    vt_result = analyze_url(url)

                    if vt_result["status"] == "sucesso":
                        malicious_count = vt_result["malicious"]
                        if malicious_count > 0:
                            final_response_text = f"ALERTA: O site {url} é MALICIOSO, detectado por {malicious_count} fornecedor(es)."
                            self.notify_user(
                                title="Ryas 🚨 URL Maliciosa",
                                message=final_response_text,
                                tags="skull",
                            )
                        else:
                            final_response_text = (
                                f"O site {url} parece seguro. Análise limpa."
                            )
                    else:
                        final_response_text = f"Falha na consulta ao VirusTotal. Detalhes: {vt_result['message']}"

                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: ANALISAR HASH (VirusTotal) ---
            elif any(k in prompt_lower for k in check_hash_keywords):
                print("LOG: Intenção detectada: Analisar Hash.")
                intent_processed = True

                hash_match = re.search(r"[a-fA-F0-9]{64}", prompt)  # SHA-256

                if not hash_match:
                    final_response_text = f"Por favor, {user_callsign}, diga o hash SHA-256 completo do arquivo para análise."
                else:
                    file_hash = hash_match.group(0)
                    self.status_update_ready.emit(
                        f"Analisando Hash: {file_hash[:10]}..."
                    )

                    vt_result = analyze_hash(file_hash)

                    if vt_result["status"] == "sucesso":
                        malicious_count = vt_result["malicious"]
                        if malicious_count > 0:
                            final_response_text = f"ALERTA: O hash é MALICIOSO, detectado por {malicious_count} fornecedor(es)."
                            self.notify_user(
                                title="Ryas 🚨 Hash Malicioso",
                                message=final_response_text,
                                tags="skull",
                            )
                        else:
                            final_response_text = f"O hash é LIMPO. Análise limpa."
                    else:
                        final_response_text = f"Falha na consulta ao VirusTotal. Detalhes: {vt_result['message']}"

                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: ADICIONAR MONITOR (Honeypot) ---
            elif any(k in prompt_lower for k in add_monitor_keywords):
                print("LOG: Intenção detectada: Adicionar Monitor (Honeypot).")
                intent_processed = True
                self.is_collecting_payload_data = True
                self.payload_creation_step = 6
                final_response_text = f"Entendido, {user_callsign}. Diga o caminho **COMPLETO** da pasta que deseja monitorar."
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: REMOVER MONITOR (Honeypot) ---
            elif any(k in prompt_lower for k in remove_monitor_keywords):
                print("LOG: Intenção detectada: Remover Monitor (Honeypot).")
                intent_processed = True
                self.is_collecting_payload_data = True
                self.payload_creation_step = 7

                current_paths_str = self._get_current_honeypot_paths(numbered=True)
                final_response_text = f"Ok, {user_callsign}. Atualmente, eu monitoro: {current_paths_str}. Qual deseja remover? (Diga o caminho completo)"
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: LISTAR MONITORES (Honeypot) ---
            elif any(k in prompt_lower for k in list_monitor_keywords):
                print("LOG: Intenção detectada: Listar Monitores (Honeypot).")
                intent_processed = True
                current_paths_str = self._get_current_honeypot_paths(numbered=True)
                final_response_text = f"Atualmente, eu estou monitorando os seguintes caminhos: {current_paths_str}"
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: TESTE DE NOTIFICAÇÃO ---
            elif (
                "teste de notificação" in prompt_lower
                or "me envie um teste" in prompt_lower
            ):
                print("LOG: Intenção detectada: Teste de Notificação.")
                intent_processed = True
                final_response_text = f"Entendido, {user_callsign}. Enviando notificação de teste para seu iPhone agora."
                self.notify_user(
                    title="Ryas 🔵 Teste de Comando de Voz",
                    message="A integração da Ryas com o ntfy está funcionando.",
                    tags="white_check_mark",
                )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: CRIAR PAYLOAD (Início) ---
            elif any(k in prompt_lower for k in payload_create_keywords) and any(
                p in prompt_lower for p in ["payload", "script"]
            ):
                print("LOG: Intenção detectada: Criar Payload (Início).")
                intent_processed = True
                words = prompt.split()
                potential_name = None
                for i, word in enumerate(words):
                    if word.lower() in ["payload", "script"] and i + 1 < len(words):
                        potential_name = words[i + 1].capitalize()
                        break
                if not potential_name:
                    final_response_text = (
                        f"{user_callsign}, qual nome para o novo payload?"
                    )
                elif potential_name in self.payload_manager.list_payloads():
                    final_response_text = (
                        f"{user_callsign}, payload '{potential_name}' já existe."
                    )
                else:
                    self.is_collecting_payload_data = True
                    self.payload_creation_step = 1
                    self.new_payload_data = {"internal_name": potential_name}
                    final_response_text = (
                        f"Ok, criando '{potential_name}'. Qual o nome do arquivo?"
                    )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: LISTAR PAYLOADS ---
            elif any(k in prompt_lower for k in payload_list_keywords) and any(
                p in prompt_lower for p in ["payloads", "scripts"]
            ):
                print("LOG: Intenção detectada: Listar Payloads.")
                intent_processed = True
                payload_names = self.payload_manager.list_payloads()
                if not payload_names:
                    final_response_text = f"{user_callsign}, nenhum payload encontrado."
                else:
                    list_prompt = (
                        f"Ryas, informe a {user_callsign} os {len(payload_names)} payloads:\n"
                        + "\n".join(
                            [
                                f"  {i + 1}. {name}"
                                for i, name in enumerate(payload_names)
                            ]
                        )
                    )
                    final_response_text = self.ai.generate_text(
                        self.chat_model, list_prompt
                    )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: DETALHES DO PAYLOAD ---
            elif any(k in prompt_lower for k in payload_details_keywords) and any(
                p in prompt_lower for p in ["payload", "script"]
            ):
                print("LOG: Intenção detectada: Detalhes.")
                intent_processed = True
                payload_name_found = self._extract_payload_name(prompt)
                if not payload_name_found:
                    final_response_text = f"{user_callsign}, especifique o nome."
                else:
                    details = self.payload_manager.get_payload_details(
                        payload_name_found
                    )
                if not details:
                    final_response_text = (
                        f"{user_callsign}, erro ao buscar '{payload_name_found}'."
                    )
                else:
                    details_formatted = (
                        f"Detalhes de '{payload_name_found}':\n"
                        + json.dumps(details, indent=2, ensure_ascii=False)
                    )
                    confirmation_prompt = f"Ryas, confirme para {user_callsign} que encontrou os detalhes de '{payload_name_found}'."
                    confirmation_response = self.ai.generate_text(
                        self.chat_model, confirmation_prompt
                    )
                    final_response_text = (
                        f"{confirmation_response}\n\n{details_formatted}"
                    )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: DELETAR PAYLOAD ---
            elif any(k in prompt_lower for k in payload_delete_keywords) and any(
                p in prompt_lower for p in ["payload", "script"]
            ):
                print("LOG: Intenção detectada: Deletar.")
                intent_processed = True
                payload_name_found = self._extract_payload_name(prompt)
                if not payload_name_found:
                    final_response_text = f"{user_callsign}, qual payload deletar?"
                else:
                    if self.payload_manager.delete_payload(
                        payload_name_found, delete_script_file=True
                    ):
                        final_response_text = f"Entendido, {user_callsign}. Payload '{payload_name_found}' deletado."
                    else:
                        final_response_text = (
                            f"{user_callsign}, não encontrei '{payload_name_found}'."
                        )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: SCAN DE REDE (Modificado) ---
            elif any(keyword in prompt_lower for keyword in network_keywords):
                print("LOG: Intenção detectada: Scan de Rede.")
                intent_processed = True
                self.status_update_ready.emit("Byakugan ativado...")
                scan_results = scan_local_network()
                if isinstance(scan_results, str):
                    final_response_text = scan_results
                    self.notify_user(
                        title="Ryas 🟡 Erro no Scan",
                        message=scan_results,
                        tags="warning",
                    )

                elif isinstance(scan_results, list):
                    num_devices = len(scan_results)
                    formatted_results = (
                        f"Scan concluído. {num_devices} dispositivos:\n"
                        + "\n".join(
                            [
                                f"  {i + 1}. IP: {d['ip']}, MAC: {d['mac']}, Fabricante: {d.get('vendor', '?')}"
                                for i, d in enumerate(scan_results)
                            ]
                        )
                    )
                    scan_prompt = f"Ryas, apresente o relatório de scan para {user_callsign}:\n{formatted_results}"
                    final_response_text = self.ai.generate_text(
                        self.chat_model, scan_prompt
                    )
                    self.notify_user(
                        title=f"Ryas 🔵 Byakugan Concluído",
                        message=f"Scan de rede encontrou {num_devices} dispositivos.",
                        tags="computer",
                    )
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: NOTÍCIAS ---
            elif any(k in prompt_lower for k in news_keywords):
                print("LOG: Intenção detectada: Notícias.")
                intent_processed = True
                self.status_update_ready.emit("Buscando notícias...")
                user_interests = self.kb_profiles.get("user", {}).get("interesses", [])

                if fetch_filtered_news is None:
                    news_results = "ERRO: Módulo 'web_tools' não encontrado."
                else:
                    try:
                        news_results = fetch_filtered_news(user_interests)
                    except Exception as e:
                        news_results = f"ERRO inesperado ao buscar notícias: {e}"

                if isinstance(news_results, str):
                    final_response_text = news_results
                elif isinstance(news_results, list):
                    if not news_results:
                        final_response_text = f"{user_callsign}, sem notícias hoje."
                    else:
                        # --- INÍCIO DA CORREÇÃO (Tradução por Voz) ---
                        formatted_news = (
                            f"Notícias ({len(news_results)}):\n"
                            + "\n".join(
                                [
                                    f"{i + 1}. {item['title']}"
                                    for i, item in enumerate(news_results)
                                ]
                            )
                        )

                        # Constrói um prompt robusto exigindo português
                        news_prompt = f"""Ryas, apresente as seguintes notícias para {user_callsign}.
**REGRA OBRIGATÓRIA:** Responda **SEMPRE e SOMENTE** em Português do Brasil. Se as notícias estiverem em inglês, TRADUZA-AS e apresente-as de forma natural.

Notícias:
{formatted_news}
"""
                        final_response_text = self.ai.generate_text(
                            self.chat_model, news_prompt
                        )
                        # --- FIM DA CORREÇÃO ---
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: GERAÇÃO DE CÓDIGO ---
            elif any(keyword in prompt_lower for keyword in code_keywords):
                print(f"LOG: Intenção detectada: Código.")
                intent_processed = True
                model_to_use = self.code_model
                final_prompt = self.system_prompt_template.format(prompt=prompt)
                final_response_text = self.ai.generate_text(model_to_use, final_prompt)
                self.ai_response_ready.emit(final_response_text)

            # --- INTENÇÃO: CHAT (PADRÃO - SEM RAG) ---
            if not intent_processed:
                print(f"LOG: Intenção detectada: Chat (Padrão).")
                model_to_use = self.chat_model
                final_prompt = self.system_prompt_template.format(prompt=prompt)
                final_response_text = self.ai.generate_text(model_to_use, final_prompt)
                self.ai_response_ready.emit(final_response_text)

        # --- LÓGICA DE FALA (UNIFICADA) ---
        if self.quick_mode_enabled:
            if final_response_text:
                print("LOG: Modo Rápido.")
            if not (
                self.is_collecting_payload_data and self.payload_creation_step != 0
            ):
                self.state_changed.emit("idle")
        elif final_response_text:
            is_honeypot_alert = "ALERTA HONEYPOT" in final_response_text

            if not (
                final_response_text.startswith("Alerta, Mestre.") and is_honeypot_alert
            ):
                self.speak_this_text.emit(final_response_text)

            if not (
                self.is_collecting_payload_data and self.payload_creation_step != 0
            ):
                pass
        else:
            if not self.is_collecting_payload_data:
                self.state_changed.emit("idle")

    def _extract_payload_name(self, prompt):
        """Tenta extrair o nome de um payload conhecido do prompt."""
        known_payloads = self.payload_manager.list_payloads()
        prompt_words = prompt.split()
        for word in prompt_words:
            if any(word.lower() == known_name.lower() for known_name in known_payloads):
                for known_name in known_payloads:
                    if word.lower() == known_name.lower():
                        print(
                            f"DEBUG: Nome encontrado por match direto: '{known_name}'"
                        )
                        return known_name
        for i, word in enumerate(prompt_words):
            if word.lower() in ["payload", "script"] and i + 1 < len(prompt_words):
                potential_name = prompt_words[i + 1]
                if any(
                    potential_name.lower() == known_name.lower()
                    for known_name in known_payloads
                ):
                    for known_name in known_payloads:
                        if potential_name.lower() == known_name.lower():
                            print(
                                f"DEBUG: Nome encontrado após keyword: '{known_name}'"
                            )
                            return known_name
        print("DEBUG: Nenhum nome de payload conhecido encontrado.")
        return None
