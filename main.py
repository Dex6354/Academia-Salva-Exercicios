import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Usamos um lock para garantir que a escrita na lista de logs seja segura entre as threads
log_lock = threading.Lock()

st.set_page_config(layout="wide")
st.title("💪 Coletor de Exercícios Otimizado")
st.write("Este script busca informações de exercícios do site `exerciciofisico.com` de forma concorrente.")
st.info("Alguns códigos podem não existir no site. O log de status detalhará quais exercícios foram encontrados e quais falharam.")

col1, col2 = st.columns(2)
with col1:
    codigo_inicial = st.number_input("Código Inicial", min_value=1, value=1)
with col2:
    codigo_final = st.number_input("Código Final", min_value=1, value=100)

if st.button("🚀 Iniciar Coleta", use_container_width=True):
    # Lista para armazenar mensagens de log de forma segura
    status_messages = []
    
    def log_status(message):
        """Adiciona uma mensagem à lista de logs de forma segura."""
        with log_lock:
            status_messages.append(message)

    def coletar_exercicio(codigo):
        """
        Coleta dados de um único exercício.
        Retorna um dicionário com os dados ou None em caso de falha.
        """
        url = f"https://exerciciofisico.com/detalhes?Codigo={codigo}"
        try:
            # Timeout aumentado para dar mais tempo para a resposta do servidor
            response = requests.get(url, timeout=10)
            # Lança uma exceção para códigos de status de erro (4xx ou 5xx)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            nome_tag = soup.find(id="lblNome1")
            
            # Validação crucial: verifica se a página realmente contém um exercício
            if not nome_tag or not nome_tag.get_text(strip=True):
                log_status(f"🟡 Aviso [{codigo}]: A página foi carregada, mas não contém dados de exercício. Ignorando.")
                return None

            descricao_tag = soup.find(id="lblDescricao")
            grupo_tag = soup.find(id="lblGrupoM")
            instrucao_tag = soup.find(id="lblInstrucao")
            
            gif_div = soup.find("div", class_="descricao-gif-grande")
            gif_tag = gif_div.find("img") if gif_div else None
            gif_url = gif_tag["src"] if gif_tag and gif_tag.has_attr("src") else ""
            
            nome_exercicio = nome_tag.get_text(strip=True)
            log_status(f"✅ Sucesso [{codigo}]: Coletado '{nome_exercicio}'")
            
            return {
                "codigo": codigo,
                "nome": nome_exercicio,
                "descricao": descricao_tag.get_text(strip=True) if descricao_tag else "",
                "grupoMuscular": grupo_tag.get_text(strip=True) if grupo_tag else "",
                "instrucao": instrucao_tag.get_text(strip=True) if instrucao_tag else "",
                "gif_url": gif_url
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                log_status(f"ℹ️ Info [{codigo}]: Exercício não encontrado no servidor (Erro 404).")
            else:
                log_status(f"🔴 Erro HTTP [{codigo}]: Falha na requisição. Status: {e.response.status_code}.")
            return None
        except requests.exceptions.RequestException as e:
            log_status(f"🔴 Erro de Rede [{codigo}]: Não foi possível acessar a URL. Detalhes: {e}")
            return None
        except Exception as e:
            log_status(f"🔴 Erro Inesperado [{codigo}]: Ocorreu um problema ao processar este item. Detalhes: {e}")
            return None

    exercicios_coletados = []
    codigos_totais = range(codigo_inicial, codigo_final + 1)
    total_a_coletar = len(codigos_totais)

    log_status(f"Iniciando a coleta de {total_a_coletar} exercícios (de {codigo_inicial} a {codigo_final})...")
    
    # Placeholder para a barra de progresso e o log
    progress_bar = st.progress(0, text="Aguardando início...")
    status_log_placeholder = st.empty()

    with ThreadPoolExecutor(max_workers=20) as executor:
        # Mapeia cada futuro ao seu código correspondente
        future_to_code = {executor.submit(coletar_exercicio, codigo): codigo for codigo in codigos_totais}
        
        resultados = []
        for i, future in enumerate(as_completed(future_to_code)):
            resultado = future.result()
            if resultado:
                resultados.append(resultado)
            
            # Atualiza a barra de progresso
            progresso_percentual = (i + 1) / total_a_coletar
            progress_bar.progress(progresso_percentual, text=f"Processando código {future_to_code[future]}... ({i+1}/{total_a_coletar})")

    # Ordena a lista final pelo código do exercício
    exercicios_coletados = sorted(resultados, key=lambda x: x["codigo"])

    log_status("🏁 Coleta de todos os exercícios concluída.")
    
    progress_bar.progress(1.0, text="Coleta Concluída!")

    # Exibe o sumário dos resultados
    st.subheader("📊 Resumo da Coleta")
    total_sucesso = len(exercicios_coletados)
    total_falha = total_a_coletar - total_sucesso

    col1, col2, col3 = st.columns(3)
    col1.metric("Tentativas", f"{total_a_coletar}")
    col2.metric("Coletados com Sucesso", f"{total_sucesso}", f"{total_sucesso/total_a_coletar:.1%}" if total_a_coletar > 0 else "0%")
    col3.metric("Falhas ou Inexistentes", f"{total_falha}", f"-{total_falha/total_a_coletar:.1%}" if total_a_coletar > 0 else "0%", delta_color="inverse")


    # Exibe o log completo no final
    with st.expander("Ver Log de Status Detalhado", expanded=False):
        # Exibe as mensagens em ordem cronológica
        st.code("\n".join(status_messages), language="log")

    if exercicios_coletados:
        st.success("Processo concluído! O arquivo foi salvo e está disponível para download.")

        json_string = json.dumps(exercicios_coletados, ensure_ascii=False, indent=2)

        # Botão de download do JSON
        st.download_button(
            label="📥 Baixar Arquivo JSON",
            data=json_string,
            file_name=f"exercicios_{codigo_inicial}_{codigo_final}.json",
            mime="application/json",
            use_container_width=True
        )

        with st.expander("Visualizar JSON Exportado"):
            st.json(exercicios_coletados)
    else:
        st.warning("Nenhum dado válido foi coletado no intervalo especificado.")
