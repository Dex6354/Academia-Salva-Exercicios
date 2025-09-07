import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

st.title("Coletor de Exercícios")
st.write("Ajuste os códigos inicial e final dos exercícios e clique em 'Iniciar Coleta'.")

col1, col2 = st.columns(2)
with col1:
    codigo_inicial = st.number_input("Código Inicial", min_value=1, value=900)
with col2:
    codigo_final = st.number_input("Código Final", min_value=1, value=908)

# Botão para iniciar o processo
if st.button("Iniciar Coleta"):

    # A lista para armazenar todas as mensagens de log
    status_messages = []

    def log_status(message):
        """Adiciona uma mensagem à lista de logs."""
        status_messages.append(message)

    def coletar_exercicio(codigo):
        """Coleta dados de um único exercício e retorna um dicionário."""
        url = f"https://exerciciofisico.com/detalhes?Codigo={codigo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                log_status(f"Erro {codigo}: Status code {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            nome_tag = soup.find(id="lblNome1")
            descricao_tag = soup.find(id="lblDescricao")
            grupo_tag = soup.find(id="lblGrupoM")
            instrucao_tag = soup.find(id="lblInstrucao")

            gif_div = soup.find("div", class_="descricao-gif-grande")
            gif_tag = gif_div.find("img") if gif_div else None
            gif_url = gif_tag["src"] if gif_tag and gif_tag.has_attr("src") else ""

            if nome_tag:
                log_status(f"Coletado: {codigo} - {nome_tag.get_text(strip=True)}")
                return {
                    "codigo": codigo,
                    "nome": nome_tag.get_text(strip=True),
                    "descricao": descricao_tag.get_text(strip=True) if descricao_tag else "",
                    "grupoMuscular": grupo_tag.get_text(strip=True) if grupo_tag else "",
                    "instrucao": instrucao_tag.get_text(strip=True) if instrucao_tag else "",
                    "gif_url": gif_url
                }
        except Exception as e:
            log_status(f"Erro ao coletar {codigo}: {e}")
            return None

    exercicios = []
    log_status("Iniciando a coleta de dados...")

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(coletar_exercicio, codigo): codigo for codigo in range(codigo_inicial, codigo_final + 1)}

        # Acompanha o progresso em tempo real, mas sem atualizar o log na tela
        for future in as_completed(futures):
            resultado = future.result()
            if resultado:
                exercicios.append(resultado)

    log_status("Coleta de todos os exercícios concluída.")
    log_status(f"Total de exercícios coletados: {len(exercicios)}")

    log_status("Salvando dados em exercicios_completo.json...")
    try:
        with open("exercicios_completo.json", "w", encoding="utf-8") as f:
            json.dump(exercicios, f, ensure_ascii=False, indent=2)
        log_status("Arquivo **exercicios_completo.json** salvo com sucesso!")

    except Exception as e:
        log_status(f"Erro ao salvar o arquivo JSON: {e}")

    # Exibe o log completo no final, dentro do expansor
    with st.expander("Log de Status", expanded=False):
        st.info("\n".join(status_messages))

    # Exibe a mensagem final de sucesso ou erro e o visualizador de JSON
    if exercicios:
        st.success("Processo concluído! O arquivo foi salvo.")
        with st.expander("Visualizar JSON Exportado"):
            st.json(exercicios)
    else:
        st.warning("Nenhum dado foi coletado para ser visualizado.")
