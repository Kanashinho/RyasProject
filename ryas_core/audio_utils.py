# /ryas_core/audio_utils.py - VERSÃO COM CALIBRAÇÃO INTELIGENTE

import speech_recognition as sr


def listen_and_transcribe():
    r = sr.Recognizer()

    # Vamos deixar o 'pause_threshold' para ele parar de gravar
    # 0.8s após você parar de falar.
    r.pause_threshold = 0.8

    with sr.Microphone() as source:
        # --- INÍCIO DA CORREÇÃO ---
        print("INFO: Calibrando para ruído ambiente (1 segundo)... Fique em silêncio.")

        # Voltamos a usar a calibração automática, mas com 1 segundo
        # para ela ter uma boa amostra do ruído de fundo (o filme).
        try:
            r.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"AVISO: Falha na calibração de ruído: {e}. Usando valores padrão.")
            r.energy_threshold = 400  # Um valor de fallback

        # --- FIM DA CORREÇÃO ---

        print(f"INFO: Limiar de energia definido para: {r.energy_threshold}")
        print("INFO: Pode falar. Ouvindo...")

        try:
            audio = r.listen(source, timeout=10, phrase_time_limit=30)
            print("INFO: Áudio capturado. Enviando para transcrição...")
            return audio

        except sr.WaitTimeoutError:
            print("ERRO: Nenhum comando de voz detectado.")
            return None
