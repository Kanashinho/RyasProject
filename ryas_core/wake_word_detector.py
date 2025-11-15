# /ryas_core/wake_word_detector.py

import struct

import pvporcupine
import pyaudio
from PyQt6.QtCore import QThread, pyqtSignal


class WakeWordDetector(QThread):
    wake_word_detected = pyqtSignal()

    def __init__(self, access_key, keyword_path, model_path):
        super().__init__()
        self.access_key = access_key
        self.keyword_path = keyword_path
        self.model_path = model_path
        self._is_running = True

    def run(self):
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keyword_paths=[self.keyword_path],
                model_path=self.model_path,
            )
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=1,  # Forçando seu microfone principal
            )
            print("LOG: Detector de palavra de ativação iniciado. Aguardando 'Ryas'...")
            while self._is_running:
                pcm = self.audio_stream.read(
                    self.porcupine.frame_length, exception_on_overflow=False
                )
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                if self.porcupine.process(pcm) >= 0:
                    print("LOG: Palavra de ativação 'Ryas' detectada!")
                    self.wake_word_detected.emit()
        except Exception as e:
            print(f"ERRO no WakeWordDetector: {e}")
        finally:
            if hasattr(self, "porcupine") and self.porcupine:
                self.porcupine.delete()
            if hasattr(self, "audio_stream") and self.audio_stream:
                self.audio_stream.close()
            if hasattr(self, "pa") and self.pa:
                self.pa.terminate()
            print("LOG: Detector de palavra de ativação encerrado.")

    def stop(self):
        self._is_running = False
        print("LOG: Solicitando encerramento do detector de palavra de ativação...")
