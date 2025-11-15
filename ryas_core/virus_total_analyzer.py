# /ryas_core/virus_total_analyzer.py

import configparser
import hashlib
from pathlib import Path
from typing import Dict, Union

import requests

# Chave de API será lida do config.ini
VT_API_KEY = None
CONFIG_PATH = Path(__file__).parent.parent / "config.ini"

# --- UTILITÁRIOS ---


def _load_api_key():
    """Carrega a chave do VirusTotal do config.ini."""
    global VT_API_KEY
    if (
        VT_API_KEY is None
        or VT_API_KEY == "ERRO_CONFIG"
        or VT_API_KEY == "COLE_SUA_CHAVE_AQUI"
    ):
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_PATH)
            VT_API_KEY = config.get("SECURITY", "VT_API_KEY").strip()
            if VT_API_KEY == "COLE_SUA_CHAVE_AQUI":
                raise Exception("Chave padrão ainda em uso.")
        except Exception:
            VT_API_KEY = "ERRO_CONFIG"


def _calculate_file_hash(filepath: str) -> Union[str, None]:
    """Calcula o hash SHA-256 de um arquivo para consulta."""
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


# --- NOVAS FUNÇÕES DE CONSULTA POR HASH E URL ---


def _vt_query(resource: str, resource_type: str) -> Dict[str, Union[str, int]]:
    """Faz a consulta genérica na API v3 (resource pode ser hash, URL, ou IP)."""
    _load_api_key()
    if VT_API_KEY in ["ERRO_CONFIG", "COLE_SUA_CHAVE_AQUI"]:
        return {"status": "erro", "message": "API Key do VirusTotal não configurada."}

    url = f"https://www.virustotal.com/api/v3/{resource_type}s/{resource}"

    headers = {"x-apikey": VT_API_KEY, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            attributes = data["data"]["attributes"]

            stats = attributes.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)

            return {
                "status": "sucesso",
                "malicious": malicious,
                "suspicious": suspicious,
                "reputation": f"{malicious} malicioso(s), {suspicious} suspeito(s)",
            }

        elif response.status_code == 404:
            return {
                "status": "nao_analisado",
                "message": "Recurso não encontrado ou nunca foi analisado no VirusTotal.",
            }
        elif response.status_code == 401:
            return {
                "status": "erro",
                "message": "Chave de API do VirusTotal inválida (401).",
            }
        else:
            return {
                "status": "erro",
                "message": f"Falha na API do VirusTotal: Código {response.status_code}.",
            }

    except requests.exceptions.RequestException:
        return {"status": "erro", "message": "Falha na conexão com o VirusTotal."}
    except Exception as e:
        return {"status": "erro", "message": f"Erro interno: {e}"}


# --- FUNÇÃO 1: ANALISAR ARQUIVO PELO CAMINHO (Atualizada para usar o _vt_query) ---


def analyze_file_by_path(filepath: str) -> Dict[str, Union[str, int]]:
    """Calcula o hash SHA-256 do arquivo e consulta o VirusTotal."""
    file_hash = _calculate_file_hash(filepath)
    if not file_hash:
        return {
            "status": "erro",
            "message": f"Não foi possível ler o arquivo: {Path(filepath).name}",
        }

    print(f"LOG [VT Analyzer]: Consultando VirusTotal para hash: {file_hash[:10]}...")
    result = _vt_query(file_hash, "file")

    if result["status"] == "sucesso":
        result["status_message"] = f"Arquivo '{Path(filepath).name}' analisado."
    elif result["status"] == "nao_analisado":
        result["status_message"] = (
            f"Arquivo '{Path(filepath).name}' nunca foi analisado no VT."
        )

    return result


# --- FUNÇÃO 2: ANALISAR URL (Nova) ---


def analyze_url(url: str) -> Dict[str, Union[str, int]]:
    """Consulta o VirusTotal para a reputação de uma URL."""
    # URLs precisam ser enviadas como hash SHA-256 da URL em formato Base64.
    # O jeito mais fácil é deixar o VT fazer o trabalho, consultando um recurso já conhecido.
    # Usaremos uma consulta de URL formatada e codificada em Base64

    # Esta é a forma mais simples (e mais robusta) de consultar a v3 API com URLs
    encoded_url = hashlib.sha256(url.encode()).hexdigest()

    print(f"LOG [VT Analyzer]: Consultando VirusTotal para URL: {url}...")
    result = _vt_query(encoded_url, "url")

    if result["status"] == "sucesso":
        result["status_message"] = f"URL '{url}' analisada."

    return result


# --- FUNÇÃO 3: ANALISAR HASH (Nova) ---


def analyze_hash(file_hash: str) -> Dict[str, Union[str, int]]:
    """Consulta o VirusTotal para a reputação de um hash de arquivo."""
    # Verifica se o hash tem o formato SHA-256 (64 caracteres hexadecimais)
    if len(file_hash) != 64 or not all(
        c in "0123456789abcdefABCDEF" for c in file_hash
    ):
        return {
            "status": "erro",
            "message": "O hash fornecido é inválido (deve ser SHA-256).",
        }

    print(f"LOG [VT Analyzer]: Consultando VirusTotal para hash: {file_hash[:10]}...")
    result = _vt_query(file_hash, "file")

    if result["status"] == "sucesso":
        result["status_message"] = f"Hash {file_hash[:10]}... analisado."

    return result


# ... (bloco if __name__ == "__main__": para testes deve ser atualizado se necessário)
