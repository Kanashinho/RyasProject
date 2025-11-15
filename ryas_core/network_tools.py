# /ryas_core/network_tools.py - VERSÃO FINAL (COM NOME DE CLASSE CORRETO)

import sys

# --- INÍCIO DA CORREÇÃO ---
# 1. O nome da classe é 'MacLookup', não 'MacVendorLookup'
from mac_vendor_lookup import MacLookup
from scapy.all import ARP, Ether, conf, srp

# --- FIM DA CORREÇÃO ---


def get_active_network_interface():
    # ... (Esta função permanece exatamente a mesma) ...
    try:
        default_route = conf.route.route("0.0.0.0", verbose=False)
        if default_route:
            interface_name = default_route[0]
            ip_address = default_route[1]
            print(
                f"LOG: Interface de rede ativa detectada: {interface_name} (IP: {ip_address})"
            )
            return interface_name, ip_address
    except Exception as e:
        print(f"ERRO: Não foi possível detectar a interface de rede ativa: {e}")
    if conf.iface:
        print("AVISO: Usando interface de rede de fallback.")
        return conf.iface.name, conf.iface.ip
    return None, None


def scan_local_network():
    print("LOG: [REDE] Iniciando scan ARP na rede local...")

    interface_name, interface_ip = get_active_network_interface()

    if not interface_name or not interface_ip:
        return "ERRO: Não foi possível determinar a interface de rede ou IP local."

    try:
        network_target = f"{interface_ip.rsplit('.', 1)[0]}.0/24"
        print(f"LOG: [REDE] Alvo do scan: {network_target}")
    except Exception as e:
        print(f"ERRO: [REDE] IP inválido para determinar a rede: {interface_ip} ({e})")
        return "ERRO: O IP da interface local não é um IPv4 válido."

    try:
        # --- INÍCIO DA CORREÇÃO ---
        # 2. Inicializa a classe com o nome correto
        mac_lookup = MacLookup()
        # --- FIM DA CORREÇÃO ---

        arp_request = ARP(pdst=network_target)
        broadcast_frame = Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast_frame / arp_request

        answered_list = srp(
            arp_request_broadcast, timeout=2, iface=interface_name, verbose=False
        )[0]

        devices = []
        for sent, received in answered_list:
            mac_address = received.hwsrc
            vendor = "Desconhecido"
            try:
                vendor = mac_lookup.lookup(mac_address)
            except Exception as e:
                if "not found" in str(e).lower() or isinstance(e, KeyError):
                    vendor = "Fabricante não encontrado (OUI desconhecido)"
                else:
                    print(f"AVISO: Falha no lookup do MAC {mac_address}: {e}")

            devices.append({"ip": received.psrc, "mac": mac_address, "vendor": vendor})

        print(f"LOG: [REDE] Scan concluído. {len(devices)} dispositivos encontrados.")

        if not devices:
            return "Nenhum dispositivo encontrado na rede local."

        return devices

    except PermissionError:
        print(
            "ERRO CRÍTICO: [REDE] Permissão negada. O script precisa ser executado como Administrador."
        )
        return "ERRO: Permissão negada. Para escanear a rede, preciso ser executada como Administrador."
    except Exception as e:
        print(f"ERRO CRÍTICO: [REDE] Falha no scan: {e}")
        return f"ERRO: Ocorreu uma falha inesperada durante o scan: {e}"
