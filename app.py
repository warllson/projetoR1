import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- SETUP E BANCO DE DADOS ---
st.set_page_config(page_title="MedFlow Pro", layout="wide")

def init_db():
    conn = sqlite3.connect('med_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS progresso 
                 (id_aula INTEGER PRIMARY KEY, status TEXT, dificuldade INTEGER, 
                  acertos REAL, ultima_data TEXT, proxima_revisao TEXT, semana TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- LÓGICA DE CARREGAMENTO (Seu CSV) ---
@st.cache_data
def load_data():
    # Carregando o arquivo Cronograma enviado
    df = pd.read_csv('Planner Extensivo MedCurso 2023 - Calendar.xlsx - Cronograma.csv', skiprows=1)
    df.columns = [c.strip() for c in df.columns]
    # Preencher semanas vazias (FFill) para manter a estrutura S1, S2...
    df['SEMANA'] = df.iloc[:, 0].fillna(method='ffill')
    return df

df_base = load_data()

# --- FUNÇÕES DE INTELIGÊNCIA ---
def calcular_revisao(dificuldade, acertos):
    hoje = datetime.now()
    # Algoritmo Adaptativo: Erros em temas difíceis voltam mais rápido
    if acertos < 60 or dificuldade >= 4:
        dias = 3
    elif acertos < 85:
        dias = 10
    else:
        dias = 30
    return (hoje + timedelta(days=dias)).strftime('%Y-%m-%d')

# --- INTERFACE WEB ---
st.sidebar.title("🩺 Menu MedFlow")
page = st.sidebar.radio("Navegação", ["Dashboard", "Estudar por Semana", "Revisões Urgentes"])

if page == "Dashboard":
    st.title("🚀 Sua Evolução")
    dados_user = pd.read_sql_query("SELECT * FROM progresso", conn)
    
    if not dados_user.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Temas Concluidos", len(dados_user))
        col2.metric("Média de Acertos", f"{dados_user['acertos'].mean():.1f}%")
        
        # Gráfico de Progresso por Semana
        fig = px.bar(dados_user, x='semana', y='acertos', color='dificuldade', title="Performance por Semana")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Comece a estudar para gerar métricas!")

elif page == "Estudar por Semana":
    semana_sel = st.selectbox("Escolha a Semana", df_base['SEMANA'].unique())
    temas = df_base[df_base['SEMANA'] == semana_sel]
    
    for _, row in temas.iterrows():
        if pd.isna(row['AULA']): continue
        
        with st.expander(f"{row['ÁREA']} - {row['AULA']}"):
            col_id, col_form = st.columns([1, 3])
            col_id.write(f"ID: {row['INDICE NUNCA ALTERE']}")
            
            with st.form(key=f"form_{row['INDICE NUNCA ALTERE']}"):
                dificuldade = st.select_slider("Dificuldade", options=[1,2,3,4,5], value=3)
                acertos = st.number_input("Acertos (%)", 0, 100, 70)
                if st.form_submit_button("Registrar Conclusão"):
                    prox = calcular_revisao(dificuldade, acertos)
                    cursor = conn.cursor()
                    cursor.execute("REPLACE INTO progresso VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (int(row['INDICE NUNCA ALTERE']), 'Concluído', dificuldade, 
                                    acertos, datetime.now().strftime('%Y-%m-%d'), prox, semana_sel))
                    conn.commit()
                    st.success(f"Registrado! Revisão sugerida para: {prox}")

elif page == "Revisões Urgentes":
    st.title("🧠 O que o algoritmo sugere para você")
    hoje = datetime.now().strftime('%Y-%m-%d')
    revisoes = pd.read_sql_query(f"SELECT * FROM progresso WHERE proxima_revisao <= '{hoje}'", conn)
    
    if revisoes.empty:
        st.success("Você está em dia com a curva de esquecimento!")
    else:
        st.warning("Estes temas estão fugindo da sua memória:")
        # Join com o df_base para pegar os nomes das aulas
        revisoes = revisoes.merge(df_base[['INDICE NUNCA ALTERE', 'AULA']], left_on='id_aula', right_on='INDICE NUNCA ALTERE')
        st.table(revisoes[['semana', 'AULA', 'acertos', 'proxima_revisao']])