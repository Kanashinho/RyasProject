# /ryas_core/hardware_monitor.py

from typing import Dict, List, Union

import psutil
import wmi

# Limites de temperatura seguros para alertas (em Celsius)
TEMP_LIMIT_CRITICAL = 90.0
TEMP_LIMIT_HIGH = 80.0


def get_system_vitals() -> Dict[str, Union[float, str]]:
    """
    Coleta as informações vitais do sistema (CPU e Memória).
    """
    vitals = {}

    # --- Uso da CPU ---
    # O interval=0.1 é importante para obter uma leitura precisa do uso.
    vitals["cpu_percent"] = psutil.cpu_percent(interval=0.1)

    # --- Memória RAM ---
    mem = psutil.virtual_memory()
    vitals["ram_percent"] = mem.percent
    vitals["ram_used_gb"] = round(mem.used / (1024**3), 2)
    vitals["ram_total_gb"] = round(mem.total / (1024**3), 2)

    # --- Uso do Disco ---
    disk = psutil.disk_usage("/")  # Monitora o disco raiz
    vitals["disk_percent"] = disk.percent

    return vitals


def get_cpu_temperatures() -> Union[float, None]:
    """
    Busca a temperatura principal (core) da CPU, usando WMI como fallback no Windows.
    """
    max_temp = 0.0
    found = False

    # 1. Tentar via PSUTIL (Método mais limpo)
    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        for sensor_name, sensor_list in temps.items():
            for entry in sensor_list:
                if hasattr(entry, "current"):
                    max_temp = max(max_temp, entry.current)
                    found = True

        if found:
            # logging.info("Temperatura lida via psutil.")
            return max_temp

    # 2. Tentar via WMI (Método específico para Windows)
    try:
        w = wmi.WMI(namespace=r"root\wmi")

        # A classe 'MSAcpi_ThermalZoneTemperature' fornece leituras de temperatura
        # O valor é dado em décimos de Kelvin.
        temperature_data = w.MSAcpi_ThermalZoneTemperature()

        for sensor in temperature_data:
            # O valor é (Temp * 10) - 2732.15 para Celsius.
            # (Ex: 2982 = 298.2 Kelvin. 298.2 - 273.15 = 25.05 Celsius)
            # Valor original: 2982
            # Valor em Celsius: (sensor.CurrentTemperature - 2732) / 10.0

            # Subtraímos 2732 (273.2 * 10) e dividimos por 10 para obter o valor em Celsius.
            celsius = (sensor.CurrentTemperature - 2732) / 10.0
            max_temp = max(max_temp, celsius)
            found = True

        if found:
            # logging.info("Temperatura lida via WMI.")
            return round(max_temp, 1)

    except Exception as e:
        # logging.error(f"Falha ao ler temperatura via WMI: {e}")
        pass  # Falha silenciosamente para retornar None

    return None  # Retorna None se ambos os métodos falharem


def get_alert_status(temp: float) -> str:
    """
    Determina o status de alerta com base na temperatura.
    """
    if temp is None:
        return "indisponível"
    elif temp >= TEMP_LIMIT_CRITICAL:
        return "CRÍTICO"
    elif temp >= TEMP_LIMIT_HIGH:
        return "ALTO"
    else:
        return "normal"


def format_alert_message(
    vitals: Dict[str, Union[float, str]], temp: float, status: str
) -> str:
    """
    Formata uma mensagem de alerta detalhada.
    """
    message = f"Status atualizado:\n"

    # Adiciona a temperatura e o status
    if status != "indisponível":
        message += f" - Temperatura da CPU: {temp}°C ({status})\n"
    else:
        message += f" - Temperatura da CPU: Indisponível\n"

    # Adiciona outros vitals
    message += f" - Uso da CPU: {vitals.get('cpu_percent', 0)}%\n"
    message += f" - Uso da RAM: {vitals.get('ram_percent', 0)}% ({vitals.get('ram_used_gb', 0)} GB)\n"

    return message
