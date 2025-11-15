import shutil

import psutil


def detect_hardware_profile():
    """Verifica o hardware e retorna 'desktop' ou 'notebook'."""

    # Critério 1: Checa a presença de uma GPU NVIDIA via comando do driver
    has_nvidia_gpu = shutil.which("nvidia-smi") is not None

    # Critério 2: Checa se a RAM total é maior que 16 GB
    total_ram_gb = psutil.virtual_memory().total / (1024**3)  # Converte bytes para GB
    has_enough_ram = total_ram_gb > 16

    if has_nvidia_gpu and has_enough_ram:
        print("INFO: GPU NVIDIA e RAM suficiente detectadas.")
        return "desktop"
    else:
        print("INFO: Hardware modesto detectado. Ativando perfil notebook.")
        return "notebook"
