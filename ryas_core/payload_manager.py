# /ryas_core/payload_manager.py

import configparser
import json
import os
from pathlib import Path

# --- NOVA IMPORTAÇÃO ---
# Importar a camada de abstração de IA (necessária para gerar código)
from .ai_abstraction import AIAbstractionLayer


class PayloadManager:
    # --- ESTA É A CORREÇÃO ---
    def __init__(self, ai_layer: AIAbstractionLayer):
        """
        Inicializa o gerenciador de payloads.
        Agora requer a camada de abstração de IA.
        """
        self.payloads_dir = Path(__file__).parent.parent / "payloads"
        self.manifest_path = self.payloads_dir / "manifest.json"
        self.payloads = self._load_manifest()
        self.ai_layer = ai_layer  # Armazena a camada de IA
        print("LOG [PayloadManager]: Manifest carregado com sucesso.")

    def _load_manifest(self):
        """Carrega o arquivo manifest.json. Cria um se não existir."""
        try:
            if not self.manifest_path.is_file():
                self.payloads_dir.mkdir(parents=True, exist_ok=True)
                with open(self.manifest_path, "w") as f:
                    json.dump({}, f)
                return {}

            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"ERRO [PayloadManager]: Falha ao carregar manifesto: {e}")
            return {}

    def _save_manifest(self):
        """Salva o dicionário de payloads no manifest.json."""
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.payloads, f, indent=4)
            return True
        except Exception as e:
            print(f"ERRO [PayloadManager]: Falha ao salvar manifesto: {e}")
            return False

    def add_payload(self, name, details):
        """Adiciona um novo payload ao manifesto e salva."""
        self.payloads[name] = details
        return self._save_manifest()

    def delete_payload(self, name, delete_script_file=False):
        """Remove um payload do manifesto e, opcionalmente, seu script."""
        if name not in self.payloads:
            return False

        if delete_script_file:
            filename = self.payloads[name].get("filename")
            if filename:
                try:
                    # (missing_ok=True) ignora erro se o arquivo já foi deletado
                    (self.payloads_dir / filename).unlink(missing_ok=True)
                    print(
                        f"LOG [PayloadManager]: Arquivo de script '{filename}' deletado."
                    )
                except Exception as e:
                    print(f"AVISO: Falha ao deletar arquivo de script: {e}")

        self.payloads.pop(name)
        return self._save_manifest()

    def list_payloads(self):
        """Retorna uma lista dos nomes de todos os payloads."""
        return list(self.payloads.keys())

    def get_payload_details(self, name):
        """Retorna o dicionário de detalhes de um payload específico."""
        return self.payloads.get(name)

    def generate_and_save_script(
        self, name: str, details: dict, code_model: str
    ) -> str:
        """
        Gera o script usando a IA de Código e o salva no diretório /payloads.
        Retorna o nome do arquivo do script gerado ou uma mensagem de erro.
        """
        filename = details.get("filename")
        language = details.get("language")
        description = details.get("description")
        target_os = ", ".join(details.get("target_os", []))
        requires_admin = "Sim" if details.get("requires_admin") else "Não"

        # 1. Construir o Prompt de Geração de Código
        prompt_template = f"""
        **Instruções OBRIGATÓRIAS (DeepSeek-Coder):**
        1. Gere APENAS o código puro solicitado. NUNCA inclua explicações, introduções ou qualquer texto antes ou depois do bloco de código.
        2. Comece a resposta imediatamente com o bloco de código (ex: ```python\\n...código...\\n```).
        3. Use {language} e inclua comentários informativos no código.
        
        **Detalhes do Script Requisitado:**
        - **Nome do Arquivo:** {filename}
        - **Linguagem:** {language}
        - **OS Alvo:** {target_os}
        - **Requer Admin:** {requires_admin}
        - **Descrição Funcional:** {description}
        
        Gere o código.
        """

        # 2. Chamar a IA de Código (usando a camada de IA que recebemos no __init__)
        raw_code = self.ai_layer.generate_code(code_model, prompt_template)

        if raw_code.startswith("ERRO:"):
            return raw_code  # Retorna a mensagem de erro

        # 3. Salvar o Arquivo de Script
        try:
            script_path = self.payloads_dir / filename

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(raw_code)

            print(f"LOG [PayloadManager]: Script '{filename}' salvo com sucesso.")
            return filename

        except Exception as e:
            print(f"ERRO [PayloadManager]: Falha ao salvar o arquivo de script: {e}")
            return (
                f"ERRO: Falha ao salvar o arquivo de script '{filename}'. Detalhes: {e}"
            )
