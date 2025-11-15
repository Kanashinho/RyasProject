# /ryas_core/transcriber.py - VERSÃO SEM LIBROSA (USA NUMPY/SOUNDFILE)

# import librosa # <-- REMOVIDO
import io  # Para manipular áudio em memória

import numpy as np
import soundfile as sf  # Usaremos para ler os dados brutos corretamente
from faster_whisper import WhisperModel
from PyQt6.QtCore import QObject, pyqtSignal


class TranscriberWorker(QObject):
    transcription_ready = pyqtSignal(str)
    status_update = pyqtSignal(str)
    model_loaded = pyqtSignal()

    def __init__(self, model_size="medium"):
        super().__init__()
        self.model_size = model_size
        self.model = None
        self.target_sample_rate = 16000

    def load_model(self):
        # ... (código de carregar modelo, sem alteração) ...
        self.status_update.emit(f"Carregando Whisper '{self.model_size}'...")
        print(f"LOG: Carregando Whisper '{self.model_size}'...")
        try:
            self.model = WhisperModel(
                self.model_size, device="cuda", compute_type="float16"
            )
            print("LOG: Whisper GPU OK.")
        except Exception as e:
            print(f"AVISO: Whisper GPU falhou ({e}). CPU...")
            self.model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8"
            )
            print("LOG: Whisper CPU OK.")
        self.status_update.emit("Pronta.")
        self.model_loaded.emit()

    def _resample_audio(self, audio_data, original_sr, target_sr):
        """Reamostra o áudio usando numpy (interpolação linear simples)."""
        print(
            f"DEBUG [Resample]: Reamostrando de {original_sr}Hz para {target_sr}Hz..."
        )
        duration = len(audio_data) / original_sr
        target_num_samples = int(duration * target_sr)

        # Cria eixos de tempo para original e alvo
        time_original = np.linspace(0, duration, len(audio_data), endpoint=False)
        time_target = np.linspace(0, duration, target_num_samples, endpoint=False)

        # Interpolação linear
        resampled_data = np.interp(time_target, time_original, audio_data)
        print(
            f"DEBUG [Resample]: Reamostragem concluída. Novo shape: {resampled_data.shape}"
        )
        return resampled_data.astype(np.float32)  # Garante float32

    def transcribe_audio(self, audio_data):
        if not self.model:
            print("ERRO: Whisper não carregado.")
            self.transcription_ready.emit("")
            return

        try:
            # --- INÍCIO DA MUDANÇA (SEM LIBROSA) ---

            # 1. Usa soundfile para ler os dados brutos e a taxa original
            #    Precisamos colocar os bytes em um buffer que soundfile entenda
            raw_bytes = audio_data.get_raw_data()
            original_sr = audio_data.sample_rate

            # Lê os bytes como áudio float32 usando soundfile
            audio_np, sr_check = sf.read(
                io.BytesIO(raw_bytes),
                dtype="float32",
                samplerate=original_sr,
                channels=1,
                format="RAW",
                subtype="PCM_16",
            )

            # Verificação de segurança
            if sr_check != original_sr:
                print(
                    f"AVISO: Sample rate lido ({sr_check}Hz) difere do esperado ({original_sr}Hz). Usando o esperado."
                )
                # Pode indicar um problema, mas continuamos com original_sr

            print(
                f"DEBUG [Transcriber]: Áudio lido com soundfile. SR={original_sr}Hz, Shape={audio_np.shape}, Dtype={audio_np.dtype}"
            )

            # 2. Reamostra se necessário usando nossa função _resample_audio
            if original_sr != self.target_sample_rate:
                audio_np = self._resample_audio(
                    audio_np, original_sr, self.target_sample_rate
                )

            # --- FIM DA MUDANÇA ---

            self.status_update.emit("Transcrevendo...")

            # 3. Envia o áudio (agora float32 e 16kHz) para o modelo
            segments, _ = self.model.transcribe(audio_np, language="pt", beam_size=5)

            text = "".join(segment.text for segment in segments).strip()
            print(f"INFO: Texto transcrito (GPU): '{text}'")
            self.transcription_ready.emit(text)

        except Exception as e:
            print(f"ERRO durante a transcrição rápida: {e}")
            self.transcription_ready.emit("")
