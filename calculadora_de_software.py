import streamlit as st
import pandas as pd
import io
import plotly.express as px
from google import genai
from google.genai.errors import APIError

# --- Configurações Iniciais da Página ---
st.set_page_config(
    page_title="Calculadora de Esforço + Análise de IA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Variáveis de Configuração ---
# Modelo GenAI a ser usado para a análise
GEMINI_MODEL = 'gemini-2.5-flash'


## 🛠️ Funções de Backend

@st.cache_data
def convert_df_to_excel(df_despesas: pd.DataFrame, df_resumo: pd.DataFrame) -> bytes:
    """Converte dois DataFrames em um arquivo Excel (.xlsx) na memória."""
    output = io.BytesIO()

    try:
        # Usa xlsxwriter como motor para compatibilidade e recursos avançados
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            
            # Escrita dos DataFrames nas abas
            df_despesas.to_excel(writer, sheet_name='Despesas Detalhadas', index=False)
            df_resumo.to_excel(writer, sheet_name='Resumo do Cálculo', index=False)
            
        return output.getvalue()
        
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: Instale 'openpyxl' e 'xlsxwriter'. Detalhes: {e}")
        return None


def simular_calculo(esforco_horas: int):
    """Gera DataFrames de exemplo com base no esforço."""
    
    # 1. DataFrame de Despesas Detalhadas (Base para a Análise da IA)
    dados_despesas = {
        'Atividade': ['Análise de Requisitos', 'Desenvolvimento de Backend', 'Desenvolvimento de Frontend', 'Testes e QA'],
        'Percentual de Horas': [0.15, 0.40, 0.30, 0.15],
        'Horas Estimadas': [esforco_horas * 0.15, esforco_horas * 0.40, esforco_horas * 0.30, esforco_horas * 0.15],
        'Custo por Hora (R$)': [150, 150, 150, 120]
    }
    df_despesas = pd.DataFrame(dados_despesas)
    df_despesas['Custo Total (R$)'] = df_despesas['Horas Estimadas'] * df_despesas['Custo por Hora (R$)']
    
    # 2. DataFrame de Resumo
    custo_total = df_despesas['Custo Total (R$)'].sum()
    horas_totais = df_despesas['Horas Estimadas'].sum()

    dados_resumo = {
        'Métrica': ['Total de Horas', 'Custo Total Estimado (R$)', 'Prazo Estimado (Semanas)'],
        'Valor': [horas_totais, custo_total, round(horas_totais / 40, 1)] 
    }
    df_resumo = pd.DataFrame(dados_resumo)
    
    return df_despesas, df_resumo

@st.cache_data(show_spinner="Analisando o esforço e gerando recomendações com Gemini...")
def gerar_analise_ia(df_despesas: pd.DataFrame, df_resumo: pd.DataFrame, api_key: str):
    """Chama a API Gemini para analisar os dados e gerar texto."""
    if not api_key:
        return "⚠️ Chave de API da Google não fornecida. Insira a chave na barra lateral para análise."

    try:
        # Inicializa o cliente da API
        client = genai.Client(api_key=api_key)
        
        # Converte os DataFrames em strings para o prompt
        prompt = f"""
        Você é um analista de projetos de software experiente. Analise o resumo do cálculo e a distribuição de despesas a seguir.
        
        ### Resumo do Projeto:
        {df_resumo.to_markdown(index=False)}

        ### Distribuição Detalhada de Despesas:
        {df_despesas.to_markdown(index=False)}

        Gere uma análise concisa focando em:
        1. **Foco do Esforço:** Quais atividades consomem a maior parte do custo/tempo (e.g., Backend, Frontend)?
        2. **Risco:** Baseado na distribuição percentual (e.g., se Testes é menor que 10%), identifique um potencial risco na estimativa.
        3. **Recomendação:** Dê uma única sugestão de otimização de custo ou tempo.
        
        Use Markdown para formatar o resultado.
        """
        
        # Chama a API
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text
    
    except APIError as e:
        return f"🚨 Erro na API do Google GenAI: Verifique sua chave de API ou as permissões. Detalhes: {e}"
    except Exception as e:
        return f"🚨 Ocorreu um erro inesperado na chamada da IA: {e}"


# --- Lógica Principal do Streamlit ---

st.title("💡 Calculadora de Esforço e Análise de IA (Gemini)")
st.markdown("Estime o esforço do projeto, visualize os custos e obtenha recomendações automáticas da IA.")

# --- Barra Lateral para Configuração da IA ---
with st.sidebar:
    st.header("🤖 Configurações da Google GenAI")
    google_api_key = st.text_input(
        "Sua Chave API (GEMINI_API_KEY)", 
        type="password", 
        help="Necessária para a análise de risco e recomendações."
    )
    
    st.markdown("---")
    st.header("⚙️ Parâmetros de Entrada")
    
    # Parâmetro de entrada principal
    esforco_total = st.slider(
        "Total de Horas Estimadas para o Projeto", 
        min_value=40, 
        max_value=1000, 
        value=240, 
        step=20,
        help="Defina o esforço total em horas (e.g., 240 horas = 6 semanas)."
    )


# Executar a simulação e obter DataFrames
df_despesas, df_resumo = simular_calculo(esforco_total)

# ------------------------------------
# 1. Análise da IA
# ------------------------------------
st.header("🧠 Análise e Sugestões da IA")

# Chama a função da IA (será executada apenas se a chave ou os dados mudarem devido ao st.cache_data)
analise_ia_text = gerar_analise_ia(df_despesas, df_resumo, google_api_key)

st.markdown(analise_ia_text)


# ------------------------------------
# 2. Exibição de Resultados e Gráfico
# ------------------------------------
col_resumo, col_grafico = st.columns([1, 2])

with col_resumo:
    st.header("📊 Resumo do Cálculo")
    st.dataframe(df_resumo, hide_index=True, use_container_width=True)

with col_grafico:
    st.header("Visualização dos Custos")
    # Criação do gráfico de pizza com Plotly
    fig = px.pie(
        df_despesas, 
        values='Custo Total (R$)', 
        names='Atividade', 
        title='Distribuição de Custo por Atividade',
        hole=.3 
    )
    st.plotly_chart(fig, use_container_width=True)

st.header("🧾 Detalhe das Despesas")
st.dataframe(df_despesas, hide_index=True, use_container_width=True)


# ------------------------------------
# 3. Botão de Download para Excel
# ------------------------------------

st.markdown("---")
st.subheader("📥 Exportação de Dados para Excel")

# Chama a função para gerar o arquivo Excel binário
excel_data = convert_df_to_excel(df_despesas, df_resumo)

if excel_data:
    st.download_button(
        label="Clique para Baixar o Arquivo Excel (.xlsx)",
        data=excel_data,
        file_name='calculadora_de_software.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        help="Baixa os DataFrames de Despesas e Resumo em duas abas separadas."
    )
