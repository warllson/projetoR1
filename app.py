import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Simulador de Residência Médica",
    page_icon="🩺",
    layout="wide"
)

BANCO = "residencia_unificada.db"

# ==============================================================================
# GERENCIAMENTO DE ESTADO (SESSÃO)
# ==============================================================================
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = 0
if 'respostas_usuario' not in st.session_state:
    st.session_state.respostas_usuario = {}
if 'mostrar_gabarito' not in st.session_state:
    st.session_state.mostrar_gabarito = False

# ==============================================================================
# FUNÇÕES DE BANCO DE DADOS
# ==============================================================================
@st.cache_data
def get_data():
    conn = sqlite3.connect(BANCO)
    # Nova Query adaptada ao Padrão Mestre
    query = """
        SELECT 
            q.id, 
            p.ano, 
            b.nome AS banca,
            q.numero, 
            q.enunciado, 
            q.alt_a, q.alt_b, q.alt_c, q.alt_d, q.alt_e, 
            q.gabarito, 
            ar.nome AS area, 
            a.nome AS tema
        FROM questoes q
        LEFT JOIN provas p ON q.prova_id = p.id
        LEFT JOIN bancas b ON p.banca_id = b.id
        LEFT JOIN assuntos a ON q.assunto_id = a.id
        LEFT JOIN areas ar ON a.area_id = ar.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Tratamento de dados nulos
    df.fillna({'alt_e': '', 'gabarito': ''}, inplace=True)
    return df

df = get_data()

# ==============================================================================
# SIDEBAR - FILTROS INTELIGENTES
# ==============================================================================
st.sidebar.title("🔍 Filtros de Estudo")

# Filtro de Banca
bancas_disponiveis = ["Todas"] + sorted(df['banca'].dropna().unique().tolist())
filtro_banca = st.sidebar.selectbox("Banca", bancas_disponiveis)

df_filtrado = df.copy()
if filtro_banca != "Todas":
    df_filtrado = df_filtrado[df_filtrado['banca'] == filtro_banca]

# Filtro de Área
areas_disponiveis = ["Todas"] + sorted(df_filtrado['area'].dropna().unique().tolist())
filtro_area = st.sidebar.selectbox("Área", areas_disponiveis)

if filtro_area != "Todas":
    df_filtrado = df_filtrado[df_filtrado['area'] == filtro_area]

# Filtro de Tema (Hierárquico)
temas_disponiveis = ["Todos"] + sorted(df_filtrado['tema'].dropna().unique().tolist())
filtro_tema = st.sidebar.selectbox("Tema", temas_disponiveis)

if filtro_tema != "Todos":
    df_filtrado = df_filtrado[df_filtrado['tema'] == filtro_tema]

# Filtro de Ano
anos_disponiveis = ["Todos"] + sorted(df_filtrado['ano'].dropna().unique().astype(str).tolist(), reverse=True)
filtro_ano = st.sidebar.selectbox("Ano", anos_disponiveis)

if filtro_ano != "Todos":
    df_filtrado = df_filtrado[df_filtrado['ano'].astype(str) == filtro_ano]

st.sidebar.markdown("---")
st.sidebar.markdown(f"**📚 Questões Filtradas: {len(df_filtrado)}**")

# Botão de Reset
if st.sidebar.button("Limpar Histórico de Respostas"):
    st.session_state.respostas_usuario = {}
    st.session_state.mostrar_gabarito = False
    st.session_state.pagina_atual = 0
    st.rerun()

# Prevenção de erro de índice ao filtrar
if st.session_state.pagina_atual >= len(df_filtrado) and len(df_filtrado) > 0:
    st.session_state.pagina_atual = 0

# ==============================================================================
# INTERFACE PRINCIPAL - ABAS
# ==============================================================================
st.title("🩺 Simulador de Residência Médica")

aba_estudo, aba_dashboard = st.tabs(["📖 Caderno de Questões", "📊 Dashboard de Desempenho"])

with aba_estudo:
    if len(df_filtrado) == 0:
        st.warning("Nenhuma questão encontrada com os filtros atuais.")
    else:
        # Carrega a questão atual
        row = df_filtrado.iloc[st.session_state.pagina_atual]
        q_id = row['id']
        
        # Cabeçalho da Questão
        st.subheader(f"Questão {row['numero']} - {row['banca']} {row['ano']}")
        st.caption(f"**Área:** {row['area']} | **Tema:** {row['tema']}")
        st.markdown("---")
        
        # Enunciado
        st.write(row['enunciado'])
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Monta alternativas dinamicamente (para lidar com PSU que pode não ter 'E')
        alternativas = []
        if pd.notna(row['alt_a']) and row['alt_a'].strip(): alternativas.append(f"A) {row['alt_a']}")
        if pd.notna(row['alt_b']) and row['alt_b'].strip(): alternativas.append(f"B) {row['alt_b']}")
        if pd.notna(row['alt_c']) and row['alt_c'].strip(): alternativas.append(f"C) {row['alt_c']}")
        if pd.notna(row['alt_d']) and row['alt_d'].strip(): alternativas.append(f"D) {row['alt_d']}")
        if pd.notna(row['alt_e']) and row['alt_e'].strip(): alternativas.append(f"E) {row['alt_e']}")
        
        # Lógica de seleção
        resposta_salva = st.session_state.respostas_usuario.get(q_id, None)
        index_selecionado = 0
        
        if resposta_salva:
            for i, alt in enumerate(alternativas):
                if alt.startswith(resposta_salva):
                    index_selecionado = i
                    break
        
        alt_selecionada = st.radio("Escolha uma alternativa:", alternativas, index=index_selecionado, key=f"radio_{q_id}")
        
        # ==============================================================================
        # BOTÕES E VALIDAÇÃO
        # ==============================================================================
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            if st.button("⬅️ Anterior", disabled=(st.session_state.pagina_atual == 0)):
                st.session_state.pagina_atual -= 1
                st.session_state.mostrar_gabarito = False
                st.rerun()
                
        with col2:
            if st.button("Responder"):
                letra_escolhida = alt_selecionada[0] # Pega o "A", "B", etc
                # Salva no formato: {'id': (letra_escolhida, area)} para o dashboard
                st.session_state.respostas_usuario[q_id] = {
                    'resposta': letra_escolhida,
                    'correta': row['gabarito'].strip().upper(),
                    'area': row['area']
                }
                st.session_state.mostrar_gabarito = True
                
        with col3:
            if st.button("Próxima ➡️", disabled=(st.session_state.pagina_atual == len(df_filtrado) - 1)):
                st.session_state.pagina_atual += 1
                st.session_state.mostrar_gabarito = False
                st.rerun()
                
        with col4:
            st.markdown(f"<div style='text-align: right; margin-top: 10px;'><b>{st.session_state.pagina_atual + 1} / {len(df_filtrado)}</b></div>", unsafe_allow_html=True)
            
        # ==============================================================================
        # FEEDBACK GABARITO
        # ==============================================================================
        if st.session_state.mostrar_gabarito or q_id in st.session_state.respostas_usuario:
            gabarito_oficial = row['gabarito'].strip().upper()
            
            # Se a questão não tiver gabarito no banco
            if not gabarito_oficial or gabarito_oficial == 'NONE':
                st.info("⚠️ Esta questão não possui gabarito cadastrado.")
            else:
                dados_resp = st.session_state.respostas_usuario.get(q_id)
                if dados_resp:
                    letra_escolhida = dados_resp['resposta']
                    if letra_escolhida == gabarito_oficial:
                        st.success(f"✅ Parabéns! Resposta Correta: {gabarito_oficial}")
                    else:
                        st.error(f"❌ Resposta Incorreta. Você escolheu {letra_escolhida}. O gabarito é: {gabarito_oficial}")


with aba_dashboard:
    st.header("📊 Análise de Desempenho")
    
    total_respondidas = len(st.session_state.respostas_usuario)
    if total_respondidas == 0:
        st.info("Comece a responder as questões para ver suas estatísticas aqui.")
    else:
        acertos = sum(1 for v in st.session_state.respostas_usuario.values() if v['resposta'] == v['correta'])
        erros = total_respondidas - acertos
        aproveitamento = (acertos / total_respondidas) * 100
        
        # Métricas Globais
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Respondidas", total_respondidas)
        m2.metric("Acertos ✅", acertos)
        m3.metric("Erros ❌", erros)
        m4.metric("Aproveitamento", f"{aproveitamento:.1f}%")
        
        st.markdown("---")
        
        # Preparando dados para o Gráfico
        dados_grafico = []
        for v in st.session_state.respostas_usuario.values():
            status = 'Acerto' if v['resposta'] == v['correta'] else 'Erro'
            dados_grafico.append({'Área': v['area'], 'Status': status})
            
        df_grafico = pd.DataFrame(dados_grafico)
        df_agrupado = df_grafico.groupby(['Área', 'Status']).size().reset_index(name='Quantidade')
        
        # Gráfico de Barras por Área
        fig = px.bar(
            df_agrupado, 
            x='Área', 
            y='Quantidade', 
            color='Status',
            title='Desempenho por Área de Estudo',
            color_discrete_map={'Acerto': '#00CC96', 'Erro': '#EF553B'},
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)