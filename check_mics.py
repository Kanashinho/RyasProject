# check_mics.py
import pyaudio

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
num_devices = info.get("deviceCount")

print("--- Dispositivos de Áudio de Entrada (Microfones) Encontrados ---")
for i in range(num_devices):
    device_info = p.get_device_info_by_host_api_device_index(0, i)
    if device_info.get("maxInputChannels") > 0:
        print(f"  --> ID do Dispositivo: {i}, Nome: {device_info.get('name')}")

p.terminate()
print("----------------------------------------------------------------")
