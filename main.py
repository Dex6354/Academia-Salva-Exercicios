import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import re

# Usamos um lock para garantir que a escrita na lista de logs seja segura entre as threads
log_lock = threading.Lock()

st.set_page_config(layout="wide")
st.title("💪 Coletor de Exercícios Resiliente")
st.write("Este script busca informações de exercícios, agora com tentativas automáticas para lidar com falhas de conexão e logs ordenados.")

st.sidebar.header("🔧 Configurações de Coleta")
codigo_inicial = st.sidebar.number_input("Código Inicial", min_value=1, value=200)
codigo_final = st.sidebar.number_input("Código Final", min_value=1, value=300)

st.sidebar.subheader("⚙️ Configurações Avançadas")
max_workers = st.sidebar.slider(
    "Nº de Conexões Simultâneas", 
    min_value=1, max_value=30, value=10,
    help="Define quantos exercícios serão baixados ao mesmo tempo. Números maiores são mais rápidos, mas aumentam o risco de bloqueios temporários pelo servidor. Se encontrar muitos erros de rede, diminua este valor."
)
max_retries = st.sidebar.slider(
    "Nº Máximo de Tentativas", 
    min_value=1, max_value=5, value=3,
    help="Quantas vezes o script tentará baixar um exercício se encontrar um erro de rede antes de desistir."
)


if st.button("🚀 Iniciar Coleta", use_container_width=True):
    # Lista para armazenar logs como tuplas (codigo, mensagem) para ordenação posterior
    status_messages = []
    
    def log_status(codigo, message):
        """Adiciona uma mensagem de log associada a um código."""
        with log_lock:
            status_messages.append((codigo, message))

    def coletar_exercicio(codigo):
        """
        Coleta dados de um único exercício com lógica de retentativas.
        """
        url = f"https://exerciciofisico.com/detalhes?Codigo={codigo}"
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status() # Lança exceção para erros HTTP (4xx, 5xx)

                # Se a requisição foi bem-sucedida, processamos o HTML
                soup = BeautifulSoup(response.text, "html.parser")
                nome_tag = soup.find(id="lblNome1")
                
                if not nome_tag or not nome_tag.get_text(strip=True):
                    log_status(codigo, f"🟡 Aviso [{codigo}]: Página carregada, mas sem dados de exercício.")
                    return None # Sucesso na requisição, mas página vazia

                descricao_tag = soup.find(id="lblDescricao")
                grupo_tag = soup.find(id="lblGrupoM")
                instrucao_tag = soup.find(id="lblInstrucao")
                gif_div = soup.find("div", class_="descricao-gif-grande")
                gif_tag = gif_div.find("img") if gif_div else None
                gif_url = gif_tag["src"] if gif_tag and gif_tag.has_attr("src") else ""
                
                nome_exercicio = nome_tag.get_text(strip=True)
                log_status(codigo, f"✅ Sucesso [{codigo}]: Coletado '{nome_exercicio}'")
                
                return {
                    "codigo": codigo, "nome": nome_exercicio,
                    "descricao": descricao_tag.get_text(strip=True) if descricao_tag else "",
                    "grupoMuscular": grupo_tag.get_text(strip=True) if grupo_tag else "",
                    "instrucao": instrucao_tag.get_text(strip=True) if instrucao_tag else "",
                    "gif_url": gif_url
                }

            except requests.exceptions.HTTPError as e:
                # Erros como 404 (Not Found) não devem ser tentados novamente.
                log_status(codigo, f"ℹ️ Info [{codigo}]: Exercício não encontrado no servidor (Erro {e.response.status_code}).")
                return None
            except requests.exceptions.RequestException as e:
                # Erros de rede (timeout, etc.) acionam a lógica de retentativa.
                wait_time = 2 ** attempt  # Espera exponencial: 1, 2, 4, 8... segundos
                log_status(codigo, f"🟠 Rede [{codigo}]: Falha na tentativa {attempt + 1}/{max_retries}. Tentando novamente em {wait_time}s...")
                time.sleep(wait_time)
        
        # Se todas as tentativas falharem
        log_status(codigo, f"🔴 Falha Final [{codigo}]: Não foi possível coletar após {max_retries} tentativas.")
        return None

    # --- INÍCIO DO PROCESSO ---
    codigos_totais = range(codigo_inicial, codigo_final + 1)
    total_a_coletar = len(codigos_totais)
    log_status(0, f"Iniciando a coleta de {total_a_coletar} exercícios (de {codigo_inicial} a {codigo_final})...")
    
    progress_bar = st.progress(0, text="Aguardando início...")
    
    resultados_finais = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {executor.submit(coletar_exercicio, codigo): codigo for codigo in codigos_totais}
        
        for i, future in enumerate(as_completed(future_to_code)):
            resultado = future.result()
            if resultado:
                resultados_finais.append(resultado)
            
            progresso_percentual = (i + 1) / total_a_coletar
            progress_bar.progress(progresso_percentual, text=f"Processando código {future_to_code[future]}... ({i+1}/{total_a_coletar})")

    progress_bar.progress(1.0, text="Coleta Concluída!")
    log_status(99999, "🏁 Coleta de todos os exercícios concluída.") # Código alto para ficar no final
    
    # Ordena a lista final de exercícios pelo código
    exercicios_coletados = sorted(resultados_finais, key=lambda x: x["codigo"])
    
    # --- EXIBIÇÃO DOS RESULTADOS ---
    st.subheader("📊 Resumo da Coleta")
    total_sucesso = len(exercicios_coletados)
    total_falha = total_a_coletar - total_sucesso

    col1, col2, col3 = st.columns(3)
    col1.metric("Tentativas", f"{total_a_coletar}")
    col2.metric("Coletados com Sucesso", f"{total_sucesso}")
    col3.metric("Falhas ou Inexistentes", f"{total_falha}")

    # Ordena os logs pelo código antes de exibir
    sorted_logs = sorted(status_messages, key=lambda x: x[0])
    log_text = "\n".join([msg for code, msg in sorted_logs])
    
    with st.expander("Ver Log de Status Detalhado (Ordenado por Código)", expanded=False):
        st.code(log_text, language="log")

    if exercicios_coletados:
        st.success("Processo concluído! O arquivo está pronto para download.")
        json_string = json.dumps(exercicios_coletados, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Baixar JSON (exercicios_completo.json)",
            data=json_string,
            file_name="exercicios_completo.json", # Nome do arquivo fixo
            mime="application/json",
            use_container_width=True
        )
        with st.expander("Visualizar JSON Exportado"):
            st.json(exercicios_coletados)
    else:
        st.warning("Nenhum dado válido foi coletado no intervalo especificado.")

