Ryas - Local AI Assistant
Um assistente de IA focado em privacidade e performance local, capaz de rodar offline.

🚀 Sobre o Projeto
O Ryas nasceu da necessidade de ter um assistente inteligente que não dependesse de nuvem, garantindo privacidade de dados e baixa latência. Diferente de wrappers simples de API, o Ryas gerencia o ciclo de vida do modelo localmente.

🛠️ Stack Tecnológica
Linguagem: Python 3.x

Core AI: Ollama / Llama 3 (Quantizado para 4-bit para otimização de memória)

Gerenciamento: Lógica customizada de inferência.

Segurança: Ambiente isolado com controle rigoroso de dependências.

💡 Desafios Técnicos Superados
Dependency Hell: Implementação de ambientes virtuais estritos e congelamento de versões (requirements.txt) para garantir reprodutibilidade em diferentes máquinas.

Otimização de Hardware: Uso de modelos quantizados (GGUF) para rodar inferência em hardware de consumo (CPUs comuns/Pen Drive) sem estourar a RAM.

Latência: Ajuste de parâmetros de geração (temperatura, top_k) para equilibrar criatividade e velocidade de resposta.

📦 Como Rodar

# 1. Clone o repo
git clone https://github.com/winter/ryas.git

# 2. Instale as dependências (Ambiente isolado)
pip install -r requirements.txt

# 3. Execute
python main.py
