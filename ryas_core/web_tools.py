# /ryas_core/web_tools.py

import time
from urllib.parse import quote_plus

import feedparser
import requests

# Removido: from bs4 import BeautifulSoup (não estava sendo usado)

# Cabeçalho para simular um navegador e evitar bloqueios simples
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def fetch_filtered_news(interests, max_items=5):
    """
    Busca notícias de um feed RSS (Google News) e filtra pelos interesses do usuário.
    Retorna uma lista de dicionários com 'title' e 'link', ou uma string de erro.
    """
    if not interests:
        return "ERRO: Não há interesses definidos na Base de Conhecimento para filtrar notícias."

    print(f"LOG [WebTools]: Buscando notícias para interesses: {interests}")

    # Monta a query para o Google News RSS (ex: "Inteligência Artificial" OR "Cibersegurança")
    # Usamos quote_plus para formatar corretamente para URL
    search_query = " OR ".join([f'"{interest}"' for interest in interests])
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(search_query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    print(f"LOG [WebTools]: URL do RSS: {rss_url}")

    try:
        # Tenta buscar o feed com timeout
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        response.raise_for_status()  # Levanta erro para status HTTP ruins (4xx, 5xx)

        # Analisa o feed RSS
        feed = feedparser.parse(response.content)

        if feed.bozo:  # feedparser usa 'bozo' para indicar um erro de parsing
            print(
                f"AVISO [WebTools]: Erro ao parsear o feed RSS: {feed.bozo_exception}"
            )
            # Tenta continuar mesmo assim, pode ter conseguido alguns itens

        filtered_news = []
        if feed.entries:
            print(f"LOG [WebTools]: {len(feed.entries)} notícias encontradas no feed.")
            # Itera pelas notícias encontradas
            for entry in feed.entries:
                title = entry.get("title", "Sem título")
                link = entry.get("link", "#")

                # Adiciona à lista
                filtered_news.append({"title": title, "link": link})

                # Para quando atingir o limite
                if len(filtered_news) >= max_items:
                    break
        else:
            print("LOG [WebTools]: Nenhuma notícia encontrada no feed para a query.")
            return f"Nenhuma notícia encontrada hoje para seus interesses ({', '.join(interests)})."

        print(f"LOG [WebTools]: Retornando {len(filtered_news)} notícias filtradas.")
        return filtered_news

    except requests.exceptions.Timeout:
        print("ERRO [WebTools]: Timeout ao buscar o feed de notícias.")
        return "ERRO: O servidor de notícias demorou muito para responder."
    except requests.exceptions.RequestException as e:
        print(f"ERRO [WebTools]: Falha ao buscar o feed de notícias: {e}")
        return f"ERRO: Não foi possível conectar ao servidor de notícias ({e})"
    except Exception as e:
        print(f"ERRO CRÍTICO [WebTools]: Erro inesperado ao processar notícias: {e}")
        return f"ERRO: Ocorreu uma falha inesperada ao buscar notícias: {e}"


# --- Teste Rápido (Opcional) ---
if __name__ == "__main__":
    print("--- Testando WebTools ---")
    test_interests = ["Inteligência Artificial", "Cibersegurança"]
    news = fetch_filtered_news(test_interests)
    print("\n--- Notícias Encontradas ---")
    if isinstance(news, list):
        for i, item in enumerate(news):
            print(f"{i + 1}. {item['title']} ({item['link']})")
    else:
        print(news)
