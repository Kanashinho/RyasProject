# /ryas_core/speech_synthesis.py - VERSÃO FINAL (Sincronização de Fala)

import os
import time
import uuid
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import torch
from PyQt6.QtCore import QObject, pyqtSignal
from TTS.api import TTS
from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig


class Speaker(QObject):
    model_loaded = pyqtSignal()
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()

    def __init__(self, use_gpu=True):
        super().__init__()
        self.use_gpu = use_gpu
        self.tts = None
        self.speaker_wav_path = str(Path(__file__).parent.parent / "speaker.wav")

    def load_voice_model(self):
        print(
            "LOG: Carregando modelo de voz Coqui 'tts_models/multilingual/multi-dataset/xtts_v2'..."
        )

        try:
            torch.serialization.add_safe_globals(
                [XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs]
            )
        except AttributeError:
            print(
                "AVISO: A versão do PyTorch não possui 'add_safe_globals'. Ignorando."
            )
            pass

        device = "cuda" if self.use_gpu else "cpu"
        print(f"LOG: Coqui TTS usará o dispositivo: {device.upper()}")

        try:
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            print("LOG: Modelo de voz Coqui carregado com sucesso.")
            self.model_loaded.emit()
        except Exception as e:
            print(f"ERRO CRÍTICO ao carregar modelo de voz: {e}")

    def say(self, text: str):
        print(f"LOG: Falando (XTTS) -> '{text[:50]}...'")
        # self.speech_started.emit()  <-- REMOVIDO DESTA LINHA

        temp_audio_path = f"temp_output_{uuid.uuid4()}.wav"

        try:
            # 1. Geração de áudio (o bloqueio de 30s)
            self.tts.tts_to_file(
                text=text,
                speaker_wav=self.speaker_wav_path,
                language="pt",
                file_path=temp_audio_path,
            )

            # 2. Carrega o áudio
            data, samplerate = sf.read(temp_audio_path, dtype="float32")

            # --- CORREÇÃO DE SINCRONIA ---
            # 3. Emite o sinal IMEDIATAMENTE ANTES de tocar
            self.speech_started.emit()
            # -----------------------------

            # 4. Toca o áudio (bloqueia até terminar)
            sd.play(data, samplerate, blocking=True)

        except Exception as e:
            print(f"ERRO durante a síntese ou reprodução de voz: {e}")
        finally:
            try:
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            except Exception as e:
                print(
                    f"AVISO: Não foi possível deletar o arquivo de áudio temporário '{temp_audio_path}'. {e}"
                )

            self.speech_finished.emit()
