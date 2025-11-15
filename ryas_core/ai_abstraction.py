import logging

import ollama


class AIAbstractionLayer:
    def __init__(self):
        """
        Inicializa a camada de abstração de IA.
        """
        print("LOG: Camada de Abstração de IA inicializada.")
        # No futuro, a seleção de Ollama vs. Outra API pode ser feita aqui.

    def generate_text(self, model_name: str, prompt: str) -> str:
        """
        Gera texto (chat) usando o modelo especificado (ex: Llama3).
        Este é o método que estava faltando.
        """
        print(f"LOG [AI]: Gerando texto com o modelo: {model_name}")
        try:
            response = ollama.generate(
                model=model_name,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": 0.7,  # Temperatura padrão para chat criativo
                    "num_ctx": 2048,
                },
            )
            return response["response"].strip()

        except ollama.exceptions.RequestError as e:
            print(f"ERRO [Ollama]: Falha ao gerar texto: {e}")
            return f"ERRO: Falha de comunicação com o servidor Ollama."
        except Exception as e:
            print(f"ERRO [AI]: Erro inesperado na geração de texto: {e}")
            return f"ERRO: Falha interna ao gerar texto."

    def generate_code(self, model_name: str, prompt: str) -> str:
        """
        Gera código usando o modelo especificado (ex: DeepSeek-Coder).
        """
        print(f"LOG [AI]: Gerando código com o modelo: {model_name}")
        try:
            response = ollama.generate(
                model=model_name,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": 0.1,  # Temperatura baixa para código preciso
                    "num_ctx": 4096,
                },
            )
            code_text = response["response"].strip()

            # --- LÓGICA DE LIMPEZA (SIMPLES E SEGURA) ---
            # Remove marcadores de código se o modelo for inconsistente
            if code_text.startswith("```"):
                code_text = (
                    code_text.replace("```python", "")
                    .replace("```Python", "")
                    .replace("```", "")
                    .strip()
                )

            return code_text

        except ollama.exceptions.RequestError as e:
            print(f"ERRO [Ollama]: Falha ao gerar código: {e}")
            return f"ERRO: Falha de comunicação com o servidor Ollama ao tentar gerar código."
        except Exception as e:
            print(f"ERRO [AI]: Erro inesperado na geração de código: {e}")
            return f"ERRO: Falha interna ao gerar código."
