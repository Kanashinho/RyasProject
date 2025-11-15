# /debug_code_gen.py
import sys

from ryas_core.ai_abstraction import AIAbstractionLayer

# Adicione esta linha (temporária) para que este script possa encontrar o ryas_core
sys.path.append("D:\Coding\Ryas_Project\ryas_core")

# --- CONFIGURAÇÕES DE TESTE (baseadas no seu log) ---
CODE_MODEL = "deepseek-coder:6.7b"
TEST_PROMPT_DETAILS = {
    "filename": "backdoor_test.py",
    "language": "python",
    "description": "Gere um script simples em Python para listar o conteúdo de uma pasta específica e salvá-lo em um arquivo de log na área de trabalho.",
    "target_os": ["windows"],
    "requires_admin": "Não",
}
# ---------------------------------------------------

ai_layer = AIAbstractionLayer()

# 1. Construir o Prompt de Geração de Código (Simulação do PayloadManager)
prompt_template = f"""
**Instruções OBRIGATÓRIAS (DeepSeek-Coder):**
1. Gere APENAS o código puro solicitado. NUNCA inclua explicações, introduções ou qualquer texto antes ou depois do bloco de código.
2. Comece a resposta imediatamente com o bloco de código (ex: ```python\\n...código...\\n```).
3. Use {TEST_PROMPT_DETAILS["language"]} e inclua comentários informativos no código.

**Detalhes do Script Requisitado:**
- **Nome do Arquivo:** {TEST_PROMPT_DETAILS["filename"]}
- **Linguagem:** {TEST_PROMPT_DETAILS["language"]}
- **OS Alvo:** {TEST_PROMPT_DETAILS["target_os"]}
- **Requer Admin:** {TEST_PROMPT_DETAILS["requires_admin"]}
- **Descrição Funcional:** {TEST_PROMPT_DETAILS["description"]}

Gere o código.
"""

print(f"--- 🧠 ENVIANDO PROMPT PARA {CODE_MODEL} ---")
print(prompt_template)
print("------------------------------------------")

# 2. Chamar a IA de Código
# NOTE: Você precisa ter certeza que o método generate_code
# na sua AIAbstractionLayer está atualizado com o código que enviei
# para o Passo 1 da Fase 6.3!

raw_output = ai_layer.generate_code(CODE_MODEL, prompt_template)

print("\n\n--- 📝 SAÍDA BRUTA DO OLLAMA (generate_code) ---")
print(raw_output)
