import streamlit as st
import pandas as pd
import io  # Necessário para a exportação de Excel na memória
import plotly.express as px  # Necessário para o gráfico
from google import genai
from google.genai.errors import APIError
import os  # Para uso geral

# --- 1. CONFIGURAÇÃO DA CHAVE E CLIENTE GEMINI ---
try:
    # Tenta carregar a chave do arquivo .streamlit/secrets.toml
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("Erro: A chave 'GEMINI_API_KEY' não foi encontrada. Configure-a na pasta .streamlit.")
    st.stop()

try:
    # Inicializa o cliente e o modelo corretamente
    client = genai.Client(api_key=api_key)
    MODEL_NAME = 'gemini-2.5-flash'
except Exception as e:
    st.error(f"Erro ao inicializar o cliente Gemini: {e}")
    st.stop()


# --- FIM DA CONFIGURAÇÃO ---


# --- FUNÇÕES ---

@st.cache_data
def processar_upload(uploaded_file):
    """Lê o arquivo CSV ou Excel e retorna um DataFrame."""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Formato de arquivo não suportado. Use .csv ou .xlsx.")
            return pd.DataFrame()

        # Tentativa de padronizar colunas para o modelo do app
        df = df.rename(columns={
            'Descrição': 'Nome',
            'Valor': 'Valor',
            'Tipo': 'Categoria'
        })

        # Filtra e formata colunas essenciais
        if 'Nome' in df.columns and 'Valor' in df.columns and 'Categoria' in df.columns:
            df = df[['Nome', 'Valor', 'Categoria']].dropna(subset=['Nome', 'Valor'])
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
        else:
            st.warning("Colunas 'Nome', 'Valor' ou 'Categoria' não encontradas no arquivo.")
            return pd.DataFrame()

        return df

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return pd.DataFrame()


@st.cache_data
def convert_df_to_excel(df):
    """Converte o DataFrame para um objeto Bytes, formatado como Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Lançamentos')
        # Opcional: Auto-ajusta a largura das colunas
        workbook = writer.book
        worksheet = writer.sheets['Lançamentos']
        for i, col in enumerate(df.columns):
            # Define o tamanho máximo da coluna (incluindo o título)
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)

    return output.getvalue()


# --- TÍTULO E LAYOUT ---
st.title("💰 App de Gestão Financeira com IA Gemini")
st.markdown("Use a barra lateral para inserir dados ou carregar um arquivo, e receba **dicas personalizadas** da IA.")

# Inicializar a lista de despesas se não existir na sessão
if 'despesas' not in st.session_state:
    st.session_state.despesas = []

# --- BARRA LATERAL (ENTRADA DE DADOS E UPLOAD) ---
st.sidebar.header("Dados Financeiros")

# 1. Renda Mensal
renda_mensal = st.sidebar.number_input("Renda Mensal (R$):", min_value=0.0, value=5000.0, step=100.0)

# 2. Upload de Arquivo
st.sidebar.subheader("Importar Lançamentos (Excel/CSV)")
uploaded_file = st.sidebar.file_uploader("Escolha um arquivo Excel (.xlsx) ou CSV", type=['csv', 'xlsx'])

if uploaded_file is not None:
    df_upload = processar_upload(uploaded_file)
    if not df_upload.empty:
        # CONCATENA: Adiciona os lançamentos do arquivo aos lançamentos existentes
        st.session_state.despesas.extend(df_upload.to_dict('records'))
        st.sidebar.success(
            f"Arquivo '{uploaded_file.name}' carregado com sucesso. {len(df_upload)} lançamentos adicionados.")
        uploaded_file = None  # Reseta o uploader para evitar re-uploads acidentais

# 3. Lançamento Manual
st.sidebar.subheader("Adicionar Lançamento Manual")
with st.sidebar.form("lancamento_form", clear_on_submit=True):
    despesa_nome = st.text_input("Nome da Despesa:")
    despesa_valor = st.number_input("Valor (R$):", min_value=0.0, value=0.0, step=10.0)
    despesa_tipo = st.selectbox("Categoria:",
                                ["Alimentação", "Moradia", "Transporte", "Lazer", "Saúde", "Educação", "Investimento",
                                 "Outros"])
    adicionar_despesa = st.form_submit_button("Adicionar Lançamento")

if adicionar_despesa and despesa_nome and despesa_valor > 0:
    st.session_state.despesas.append({
        'Nome': despesa_nome,
        'Valor': despesa_valor,
        'Categoria': despesa_tipo
    })
    st.sidebar.success(f"Despesa '{despesa_nome}' adicionada!")

# --- VISUALIZAÇÃO PRINCIPAL E CÁLCULOS ---
st.header("Resumo Atual e Detalhes")

df_despesas = pd.DataFrame(st.session_state.despesas)

# Cálculos
total_despesas = df_despesas['Valor'].sum() if not df_despesas.empty else 0.0
saldo = renda_mensal - total_despesas

col1, col2, col3 = st.columns(3)
col1.metric(label="Renda Mensal", value=f"R$ {renda_mensal:,.2f}")
col2.metric(label="Total de Despesas", value=f"R$ {total_despesas:,.2f}")
col3.metric(label="Saldo Restante", value=f"R$ {saldo:,.2f}",
            delta=f"{saldo:,.2f}", delta_color="normal" if saldo >= 0 else "inverse")

st.subheader("Lançamentos Detalhados")
st.dataframe(df_despesas, use_container_width=True)

# -----------------------------------------------------------
# --- EXPORTAÇÃO E GRÁFICO (Se houver dados) ---
# -----------------------------------------------------------

if not df_despesas.empty:
    col_download: object
    col_chart, col_download = st.columns([2, 1])

    # 1. GRÁFICO DE PIZZA
    with col_chart:
        st.subheader("Distribuição de Gastos")
        df_agrupado = df_despesas.groupby('Categoria')['Valor'].sum().reset_index()

        fig = px.pie(
            df_agrupado,
            values='Valor',
            names='Categoria',
            title='Percentual de Gastos por Categoria',
            hole=.3
        )
        fig.update_traces(textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)



    with col_download:
        st.write("")  # Espaço
        st.write("")  # Espaço
        st.write("")  # Espaço
        excel_data = convert_df_to_excel(df_despesas)

    st.download_button(
        label="📥 Exportar Dados para Excel (.xlsx)",
        data=excel_data,
        file_name='gestao_financeira_export.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        help="Baixa todos os lançamentos atualmente exibidos."
    )

# --- SEÇÃO DE DICAS DA IA GEMINI ---
st.header("✨ Dicas de Melhor Gestão Financeira com IA Gemini")

if st.button("Gerar Análise e Dicas do Gemini"):
    if not st.session_state.despesas:
        st.warning("Por favor, adicione ou carregue pelo menos uma despesa para receber dicas personalizadas.")
    else:
        try:
            # 1. Preparar o prompt
            prompt = f"""
             Você é um consultor financeiro. Analise a seguinte situação financeira:
             - Renda Mensal: R$ {renda_mensal:,.2f}
             - Saldo Atual: R$ {saldo:,.2f}
             - Despesas por Categoria (para análise detalhada):
              {df_despesas.groupby('Categoria')['Valor'].sum().sort_values(ascending=False).to_string()}

             Gere 4 dicas práticas, personalizadas e motivacionais para melhorar a gestão financeira do usuário. 
             Se o saldo for negativo, a prioridade é sugerir cortes específicos. Se for positivo, foque em aumentar reservas e oportunidades de investimento.
             Formate a resposta como uma lista numerada usando Markdown.
             """

            with st.spinner('A IA Gemini está analisando seus dados e gerando seu plano de ação...'):
                # 2. CHAMA O MODELO
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )

                # 3. Exibir a resposta
                st.success("Análise e Plano de Ação Concluídos!")
                st.markdown(response.text)
        except APIError:
            st.error("Erro ao conectar com a API Gemini. Verifique sua chave de API e sua conexão com a internet.")
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")