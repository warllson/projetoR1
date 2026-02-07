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
    # Tabela de simulados (velocidade)
    c.execute('''CREATE TABLE IF NOT EXISTS simulados 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, area TEXT, 
                  questoes INTEGER, tempo_minutos INTEGER, acertos_pct REAL)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. CARREGAMENTO E TRATAMENTO DE DADOS
# ==========================================
@st.cache_data
def load_planner():
    # Carrega o arquivo Cronograma enviado
    file_path = 'Planner Extensivo MedCurso 2023 - Calendar.xlsx - Cronograma.csv'
    try:
        df = pd.read_csv(file_path, skiprows=1)
        df.columns = [c.strip() for c in df.columns]
        # Preenchimento inteligente das semanas (S1, S2, S3...)
        df['SEMANA'] = df.iloc[:, 0].fillna(method='ffill')
        return df
    except FileNotFoundError:
        st.error(f"Arquivo {file_path} não encontrado na pasta!")
        return pd.DataFrame()

df_base = load_planner()

# ==========================================
# 3. LÓGICA DE INTELIGÊNCIA (ALGORITMOS)
# ==========================================
def calcular_proxima_revisao(dificuldade, acertos):
    hoje = datetime.now()
    # Se acerto for baixo (<70%) ou dificuldade alta (4-5), revisa rápido
    if acertos < 70 or dificuldade >= 4:
        intervalo = 7
    elif acertos < 85:
        intervalo = 15
    else:
        intervalo = 30
    return (hoje + timedelta(days=intervalo)).strftime('%Y-%m-%d')

AREAS_ALTA_INCIDENCIA = ['PEDIATRIA', 'GINECOLOGIA', 'OBSTETRÍCIA', 'PREVENTIVA', 'CIRURGIA']

# ==========================================
# 4. INTERFACE DO USUÁRIO (UI)
# ==========================================
st.sidebar.title("🩺 MedFlow Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Cronograma Semanal", "Revisões de Hoje", "Modo Simulado (Velocidade)"])

# --- ABA 1: DASHBOARD ---
if menu == "Dashboard":
    st.title("🚀 Central de Inteligência de Estudos")
    
    # Busca dados do banco
    df_prog = pd.read_sql_query("SELECT * FROM progresso", conn)
    
    if not df_prog.empty:
        # Métricas Principais
        col1, col2, col3 = st.columns(3)
        col1.metric("Aulas Concluídas", len(df_prog))
        col2.metric("Média Geral de Acertos", f"{df_prog['acertos'].mean():.1f}%")
        
        # Alertas de Áreas Críticas
        st.subheader("⚠️ Alertas de Performance (Gaps de Aprovação)")
        # Join para pegar os nomes das áreas
        df_merged = df_prog.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], 
                                  left_on='id_aula', right_on='INDICE NUNCA ALTERE')
        
        alertas = df_merged[(df_merged['ÁREA'].str.upper().isin(AREAS_ALTA_INCIDENCIA)) & (df_merged['acertos'] < 75)]
        
        if not alertas.empty:
            st.error(f"Você tem {len(alertas)} temas cruciais com aproveitamento abaixo de 75%!")
            st.dataframe(alertas[['SEMANA', 'ÁREA', 'AULA', 'acertos']])
        else:
            st.success("Excelente! Suas áreas de alta incidência estão dentro da meta.")

        # Gráfico de Evolução
        fig = px.line(df_prog, x='data_conclusao', y='acertos', title="Sua Curva de Performance")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado registrado ainda. Comece pelo Cronograma Semanal!")

# --- ABA 2: CRONOGRAMA ---
elif menu == "Cronograma Semanal":
    st.title("📅 Planejamento MedCurso")
    
    semana = st.selectbox("Escolha a Semana de Estudo", df_base['SEMANA'].unique())
    aulas_semana = df_base[df_base['SEMANA'] == semana]
    
    for _, row in aulas_semana.iterrows():
        if pd.isna(row['AULA']): continue
        
        with st.expander(f"📖 {row['ÁREA']} - {row['AULA']}"):
            with st.form(key=f"form_{row['INDICE NUNCA ALTERE']}"):
                col_d, col_a = st.columns(2)
                dif = col_d.select_slider("Dificuldade", options=[1, 2, 3, 4, 5], value=3)
                acertos = col_a.number_input("Acertos (%)", 0, 100, 75)
                
                if st.form_submit_button("Registrar Estudo"):
                    prox_data = calcular_proxima_revisao(dif, acertos)
                    cursor = conn.cursor()
                    cursor.execute("REPLACE INTO progresso VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (int(row['INDICE NUNCA ALTERE']), 'Concluído', dif, acertos, 
                                    datetime.now().strftime('%Y-%m-%d'), prox_data, semana))
                    conn.commit()
                    st.success(f"Registrado! Próxima revisão agendada para {prox_data}")

# --- ABA 3: REVISÕES ---
elif menu == "Revisões de Hoje":
    st.title("🧠 O que sua memória precisa hoje")
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    rev_sql = f"SELECT * FROM progresso WHERE proxima_revisao <= '{hoje}'"
    df_rev = pd.read_sql_query(rev_sql, conn)
    
    if df_rev.empty:
        st.balloons()
        st.success("Tudo revisado! Você está em dia com a curva de esquecimento.")
    else:
        df_rev_completo = df_rev.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], 
                                      left_on='id_aula', right_on='INDICE NUNCA ALTERE')
        st.warning(f"Você tem {len(df_rev_completo)} revisões pendentes para consolidar a memória.")
        st.table(df_rev_completo[['SEMANA', 'ÁREA', 'AULA', 'acertos', 'proxima_revisao']])

# --- ABA 4: MODO SIMULADO ---
elif menu == "Modo Simulado (Velocidade)":
    st.title("⏱️ Treinamento de Velocidade de Prova")
    st.markdown("A meta média das grandes provas é de **120 segundos (2 minutos)** por questão.")
    
    with st.form("simulado_vel"):
        col_q, col_t = st.columns(2)
        q_total = col_q.number_input("Quantidade de Questões", 1, 200, 50)
        t_total = col_t.number_input("Tempo Gasto (Minutos)", 1, 600, 100)
        nota = st.slider("Nota Final (%)", 0, 100, 75)
        
        if st.form_submit_button("Analisar Velocidade"):
            segundos_por_questao = (t_total * 60) / q_total
            
            if segundos_por_questao <= 120:
                st.success(f"Velocidade Excelente: {segundos_por_questao:.1f} segundos por questão.")
            else:
                st.warning(f"Velocidade Alerta: {segundos_por_questao:.1f}s por questão. Você está acima dos 120s ideais.")
            
            # Salva histórico de simulado
            c = conn.cursor()
            c.execute("INSERT INTO simulados (data, questoes, tempo_minutos, acertos_pct) VALUES (?, ?, ?, ?)",
                      (datetime.now().strftime('%Y-%m-%d'), q_total, t_total, nota))
            conn.commit()
            st.info("Simulado registrado no seu histórico de performance.")
