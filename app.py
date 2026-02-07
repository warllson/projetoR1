import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# ==========================================
# 1. SETUP E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="MedFlow Ultra-Específico", layout="wide")

def init_db():
    conn = sqlite3.connect('medflow_vfinal.db', check_same_thread=False)
    c = conn.cursor()
    # Tabela de progresso principal
    c.execute('''CREATE TABLE IF NOT EXISTS progresso 
                 (id_aula INTEGER PRIMARY KEY, status TEXT, dificuldade INTEGER, 
                  acertos REAL, data_conclusao TEXT, proxima_revisao TEXT, 
                  semana TEXT, urgencia_simulado INTEGER DEFAULT 0)''')
    # Tabela de simulados específicos por assunto
    c.execute('''CREATE TABLE IF NOT EXISTS simulados 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, id_aula INTEGER, 
                  acertos_pct REAL, tempo_minutos INTEGER)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. CARREGAMENTO E LIMPEZA DE DADOS
# ==========================================
@st.cache_data
def load_planner():
    file_path = 'Planner Extensivo MedCurso 2023 - Calendar.xlsx - Cronograma.csv'
    try:
        # Pula as 2 linhas de cabeçalho do MedCurso
        df = pd.read_csv(file_path, skiprows=2)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Ajusta nome da coluna de semana e preenche para baixo
        if 'Unnamed: 0' in df.columns:
            df = df.rename(columns={'Unnamed: 0': 'SEMANA_REF'})
        df['SEMANA'] = df['SEMANA_REF'].ffill()
        
        # Remove linhas sem aula definida
        df = df.dropna(subset=['AULA'])
        # Garante que o ID seja inteiro
        df['INDICE NUNCA ALTERE'] = df['INDICE NUNCA ALTERE'].astype(int)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

df_base = load_planner()

# ==========================================
# 3. ALGORITMOS DE REVISÃO (SRS)
# ==========================================
def calcular_revisao(dificuldade, acertos, urgencia=0):
    hoje = datetime.now()
    # Prioridade máxima para erro em simulado específico
    if urgencia == 1:
        intervalo = 2 
    elif acertos < 70 or dificuldade >= 4:
        intervalo = 7
    elif acertos < 85:
        intervalo = 14
    else:
        intervalo = 30
    return (hoje + timedelta(days=intervalo)).strftime('%Y-%m-%d')

# ==========================================
# 4. INTERFACE WEB (UI/UX)
# ==========================================
st.sidebar.title("🩺 MedFlow Intelligence")
menu = st.sidebar.radio("Navegação", ["Dashboard & Heatmap", "Estudo Semanal", "Revisões (SRS)", "Diagnóstico Específico"])

if df_base.empty:
    st.error("Base de dados não encontrada. Verifique o arquivo CSV.")
else:
    # --- DASHBOARD COM HEATMAP ---
    if menu == "Dashboard & Heatmap":
        st.title("📊 Visão de Águia: Diagnóstico Visual")
        df_p = pd.read_sql_query("SELECT * FROM progresso", conn)
        
        if not df_p.empty:
            df_m = df_p.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], left_on='id_aula', right_on='INDICE NUNCA ALTERE')
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Aulas Concluídas", len(df_p))
            c2.metric("Média de Acertos", f"{df_p['acertos'].mean():.1f}%")
            c3.metric("Alertas de Urgência", len(df_p[df_p['urgencia_simulado'] == 1]))

            # Heatmap de Performance
            st.subheader("🔥 Mapa de Calor: Áreas Críticas")
            st.info("Este gráfico correlaciona Dificuldade (eixo Y) com Acertos (eixo X). Bolhas maiores e vermelhas são seus maiores gaps.")
            
            fig = px.scatter(df_m, x="acertos", y="dificuldade", size="dificuldade", color="acertos",
                             hover_name="AULA", title="Análise de Gap: Dificuldade vs Aproveitamento",
                             color_continuous_scale=px.colors.sequential.RdBu_r)
            st.plotly_chart(fig, use_container_width=True)
            
            

        else:
            st.info("Registre seus estudos para gerar o Mapa de Calor.")

    # --- REGISTRO SEMANAL ---
    elif menu == "Estudo Semanal":
        st.title("📅 Registro de Conteúdo Novo")
        semanas = [s for s in df_base['SEMANA'].unique() if pd.notna(s)]
        sem_sel = st.selectbox("Escolha a Semana", semanas)
        
        for _, row in df_base[df_base['SEMANA'] == sem_sel].iterrows():
            with st.expander(f"📖 {row['AULA']}"):
                with st.form(key=f"f_{row['INDICE NUNCA ALTERE']}"):
                    d_val = st.select_slider("O quanto você sofreu nesse tema? (1-Fácil, 5-Hard)", options=[1,2,3,4,5], value=3)
                    a_val = st.number_input("Acertos na lista de questões (%)", 0, 100, 80)
                    if st.form_submit_button("Salvar Progresso"):
                        prox = calcular_revisao(d_val, a_val)
                        conn.execute("REPLACE INTO progresso (id_aula, status, dificuldade, acertos, data_conclusao, proxima_revisao, semana, urgencia_simulado) VALUES (?,?,?,?,?,?,?,?)",
                                   (int(row['INDICE NUNCA ALTERE']), 'Concluído', d_val, a_val, datetime.now().strftime('%Y-%m-%d'), prox, sem_sel, 0))
                        conn.commit()
                        st.success(f"Registrado! Próxima revisão em {prox}")

    # --- REVISÕES ---
    elif menu == "Revisões (SRS)":
        st.title("🧠 Curva de Esquecimento Ativa")
        hoje = datetime.now().strftime('%Y-%m-%d')
        df_r = pd.read_sql_query(f"SELECT * FROM progresso WHERE proxima_revisao <= '{hoje}'", conn)
        
        if df_r.empty:
            st.balloons()
            st.success("Tudo revisado! Sua memória está em dia.")
        else:
            df_r = df_r.merge(df_base[['INDICE NUNCA ALTERE', 'ÁREA', 'AULA']], left_on='id_aula', right_on='INDICE NUNCA ALTERE')
            st.warning("Temas que precisam de atenção hoje:")
            # Estilizando para destacar urgências
            st.dataframe(df_r[['urgencia_simulado', 'ÁREA', 'AULA', 'acertos', 'proxima_revisao']].sort_values('urgencia_simulado', ascending=False))

    # --- DIAGNÓSTICO ESPECÍFICO ---
    elif menu == "Diagnóstico Específico":
        st.title("🎯 Diagnóstico de Precisão (Assunto)")
        st.markdown("Use esta aba quando fizer um simulado geral e errar uma questão de um **tema específico**.")
        
        c1, c2 = st.columns(2)
        area_f = c1.selectbox("Filtrar Área", df_base['ÁREA'].unique())
        aula_f = c2.selectbox("Selecione o Assunto Exato do Erro", df_base[df_base['ÁREA'] == area_f]['AULA'].unique())
        
        row_sel = df_base[df_base['AULA'] == aula_f].iloc[0]
        id_target = int(row_sel['INDICE NUNCA ALTERE'])
        
        with st.form("diag_form"):
            nota_err = st.slider("Desempenho no simulado para este tema (%)", 0, 100, 50)
            if st.form_submit_button("Aplicar Re-rating"):
                # Se nota for baixa, ativa urgência e puxa revisão para daqui a 2 dias
                if nota_err < 75:
                    prox_urgente = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                    conn.execute("UPDATE progresso SET urgencia_simulado = 1, proxima_revisao = ? WHERE id_aula = ?", (prox_urgente, id_target))
                    st.error(f"PONTO FALHO DETECTADO! O tema '{aula_f}' foi movido para revisão prioritária em 48h.")
                else:
                    st.success("Nota dentro da meta. Mantendo cronograma original.")
                conn.commit()
