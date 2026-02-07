import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# ==========================================
# 1. CONFIGURAÇÕES E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="MedFlow Pro - Gestão de Residência", layout="wide")

def init_db():
    conn = sqlite3.connect('medflow_data.db', check_same_thread=False)
    c = conn.cursor()
    # Tabela de progresso das aulas
    c.execute('''CREATE TABLE IF NOT EXISTS progresso 
                 (id_aula INTEGER PRIMARY KEY, status TEXT, dificuldade INTEGER, 
                  acertos REAL, data_conclusao TEXT, proxima_revisao TEXT, semana TEXT)''')
    # Tabela de simulados
    c.execute('''CREATE TABLE IF NOT EXISTS simulados 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, questoes INTEGER, 
                  tempo_minutos INTEGER, acertos_pct REAL)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. CARREGAMENTO E TRATAMENTO DE DADOS (CORRIGIDO)
# ==========================================
@st.cache_data
def load_planner():
    file_path = 'Planner Extensivo MedCurso 2023 - Calendar.xlsx - Cronograma.csv'
    try:
        # Pula as 2 primeiras linhas para ler os nomes das colunas corretamente
        df = pd.read_csv(file_path, skiprows=2)
        
        # Limpa espaços em branco dos nomes das colunas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Renomeia a primeira coluna vazia para 'SEMANA_REF' (onde ficam S1, S2...)
        if 'Unnamed: 0' in df.columns:
            df = df.rename(columns={'Unnamed: 0': 'SEMANA_REF'})
        else:
            # Garante que a primeira coluna seja a nossa referência de semana
            df.rename(columns={df.columns[0]: 'SEMANA_REF'}, inplace=True)
            
        # Preenche as semanas para baixo (S1, S1, S1, S2, S2...)
        df['SEMANA'] = df['SEMANA_REF'].ffill()
        
        # Remove linhas que não são aulas reais (linhas vazias no CSV)
        df = df.dropna(subset=['AULA'])
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        return pd.DataFrame()

df_base = load_planner()

# ==========================================
# 3. LÓGICA DE INTELIGÊNCIA
# ==========================================
def calcular_proxima_revisao(dificuldade, acertos):
    hoje = datetime.now()
    if acertos < 70 or dificuldade >= 4:
        intervalo = 7
    elif acertos < 85:
        intervalo = 15
    else:
        intervalo = 30
    return (hoje + timedelta(days=intervalo)).strftime('%Y-%m-%d')

AREAS_ALTA_INCIDENCIA = ['PEDIATRIA', 'GINECOLOGIA', 'OBSTETRÍCIA', 'PREVENTIVA', 'CIRURGIA']

# ==========================================
# 4. INTERFACE DO USUÁRIO
# ==========================================
st.sidebar.title("🩺 MedFlow Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Cronograma Semanal", "Revisões de Hoje", "Modo Simulado (Velocidade)"])

if df_base.empty:
    st.warning("Aguardando carregamento do arquivo CSV...")
else:
    # --- ABA 1: DASHBOARD ---
    if menu == "Dashboard":
        st.title("🚀 Sua Evolução")
        df_prog = pd.read_sql_query("SELECT * FROM progresso", conn)
        
        if not df_prog.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Aulas Concluídas", len(df_prog))
            col2.metric("Média Geral de Acertos", f"{df_prog['acertos'].mean():.1f}%")
            
            # Alertas
            st.subheader("⚠️ Alertas de Áreas Críticas")
            df_merged = df_prog.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], 
                                      left_on='id_aula', right_on='INDICE NUNCA ALTERE')
            
            alertas = df_merged[(df_merged['ÁREA'].str.upper().str.contains('|'.join(AREAS_ALTA_INCIDENCIA), na=False)) & (df_merged['acertos'] < 75)]
            
            if not alertas.empty:
                st.error(f"Foco aqui! {len(alertas)} temas de alta incidência estão abaixo de 75%.")
                st.dataframe(alertas[['SEMANA', 'ÁREA', 'AULA', 'acertos']])
            
            fig = px.line(df_prog.sort_values('data_conclusao'), x='data_conclusao', y='acertos', title="Sua Curva de Performance")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Registre sua primeira aula no menu 'Cronograma Semanal' para ver os dados.")

    # --- ABA 2: CRONOGRAMA ---
    elif menu == "Cronograma Semanal":
        st.title("📅 Planejamento por Semana")
        # Filtra apenas semanas válidas
        semanas_validas = [s for s in df_base['SEMANA'].unique() if pd.notna(s)]
        semana_sel = st.selectbox("Escolha a Semana", semanas_validas)
        
        aulas_semana = df_base[df_base['SEMANA'] == semana_sel]
        
        for _, row in aulas_semana.iterrows():
            with st.expander(f"📖 {row['ÁREA']} - {row['AULA']}"):
                with st.form(key=f"form_{row['INDICE NUNCA ALTERE']}"):
                    col_d, col_a = st.columns(2)
                    dif = col_d.select_slider("Dificuldade", options=[1, 2, 3, 4, 5], value=3)
                    acertos = col_a.number_input("Acertos (%)", 0, 100, 75)
                    
                    if st.form_submit_button("Salvar Progresso"):
                        prox_data = calcular_proxima_revisao(dif, acertos)
                        c = conn.cursor()
                        c.execute("REPLACE INTO progresso VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (int(row['INDICE NUNCA ALTERE']), 'Concluído', dif, acertos, 
                                    datetime.now().strftime('%Y-%m-%d'), prox_data, semana_sel))
                        conn.commit()
                        st.success(f"Aula {row['INDICE NUNCA ALTERE']} salva! Próxima revisão: {prox_data}")

    # --- ABA 3: REVISÕES ---
    elif menu == "Revisões de Hoje":
        st.title("🧠 Revisões Baseadas na Curva de Esquecimento")
        hoje = datetime.now().strftime('%Y-%m-%d')
        df_rev = pd.read_sql_query(f"SELECT * FROM progresso WHERE proxima_revisao <= '{hoje}'", conn)
        
        if df_rev.empty:
            st.success("Tudo em dia! Aproveite para avançar no cronograma.")
        else:
            df_rev_completo = df_rev.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], 
                                          left_on='id_aula', right_on='INDICE NUNCA ALTERE')
            st.warning(f"Priorize estes {len(df_rev_completo)} temas hoje:")
            st.table(df_rev_completo[['SEMANA', 'ÁREA', 'AULA', 'acertos', 'proxima_revisao']])

    # --- ABA 4: MODO SIMULADO ---
    elif menu == "Modo Simulado (Velocidade)":
        st.title("⏱️ Treino de Agilidade")
        with st.form("simulado_vel"):
            col_q, col_t = st.columns(2)
            q_total = col_q.number_input("Total de Questões", 1, 100, 50)
            t_total = col_t.number_input("Tempo Total (Minutos)", 1, 300, 100)
            nota = st.slider("Aproveitamento (%)", 0, 100, 75)
            
            if st.form_submit_button("Analisar"):
                seg_per_q = (t_total * 60) / q_total
                if seg_per_q <= 120:
                    st.success(f"Ótimo tempo! {seg_per_q:.1f} segundos por questão.")
                else:
                    st.warning(f"Cuidado! {seg_per_q:.1f}s por questão. O ideal é abaixo de 120s.")
