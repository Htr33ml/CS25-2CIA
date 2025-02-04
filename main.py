import streamlit as st
import pandas as pd
import gspread
import json
import os
import sys
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import hashlib
from pytz import timezone  # Para trabalhar com fusos horários

# Define o fuso horário de Brasília
brasilia_tz = timezone('America/Sao_Paulo')

# ------------------------------
# CONFIGURAÇÃO DO GOOGLE SHEETS
# ------------------------------
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS_JSON')
if not creds_json:
    sys.exit("Erro: A variável de ambiente 'GOOGLE_SHEET_CREDENTIALS_JSON' não está definida.")

creds_dict = json.loads(creds_json)  # Carrega as credenciais como dicionário JSON
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Planilha principal com os dados dos conscritos (primeira aba)
sheet = client.open("Relatório de Conscritos").sheet1
# Planilha com os usuários para login (aba "Usuarios")
users_sheet = client.open("Relatório de Conscritos").worksheet("Usuarios")
# Planilha para registrar logins (aba "Logins")
try:
    logins_sheet = client.open("Relatório de Conscritos").worksheet("Logins")
except gspread.exceptions.WorksheetNotFound:
    sys.exit("Erro: A aba 'Logins' não foi encontrada. Crie-a na planilha.")

# ------------------------------
# FUNÇÕES DE AUTENTICAÇÃO
# ------------------------------
def hash_senha(senha):
    return hashlib.sha256(senha.strip().encode()).hexdigest()

def autenticar_usuario(usuario, senha):
    usuarios = users_sheet.get_all_values()
    if len(usuarios) < 2:
        return False
    df_usuarios = pd.DataFrame(usuarios[1:], columns=usuarios[0])
    df_usuarios = df_usuarios.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    if usuario not in df_usuarios['usuario'].values:
        return False
    user_row = df_usuarios[df_usuarios['usuario'] == usuario].iloc[0]
    senha_digitada_hash = hash_senha(senha)
    if user_row['senha'] == senha_digitada_hash:
        return True
    if user_row['senha'] == senha:
        linha_usuario = df_usuarios.index[df_usuarios['usuario'] == usuario][0] + 2
        users_sheet.update_cell(linha_usuario, 2, senha_digitada_hash)
        return True
    return False

def login():
    st.title("Login - Seleção Complementar 2025")
    usuario = st.text_input("Usuário:")
    senha = st.text_input("Senha:", type="password")
    if st.button("Entrar"):
        if autenticar_usuario(usuario, senha):
            st.session_state['usuario'] = usuario
            st.session_state['logado'] = True
            data_hora = datetime.now(brasilia_tz).strftime("%Y-%m-%d %H:%M:%S")
            logins_sheet.append_row([usuario, data_hora])
            st.success(f"✅Bem-vindo, {usuario}!")
            st.rerun()
        else:
            st.error("❌Usuário ou senha incorretos. Confira Espaços! Tente novamente.")

if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
    st.stop()

# ------------------------------
# CABEÇALHO SUPERIOR FIXO (Imagem, Título e Subtítulo Centralizados)
# ------------------------------
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image('IMG_1118.png', width=200)
st.markdown('<h1>SELEÇÃO COMPLEMENTAR 2025</h1>', unsafe_allow_html=True)
st.markdown('<h2>2ª CIA - TIGRE</h2>', unsafe_allow_html=True)
st.markdown("</div><hr>", unsafe_allow_html=True)

# ------------------------------
# FUNÇÃO AUXILIAR: Converter "Sim"/"Não" em 1/0
# ------------------------------
def conv(x):
    return 1 if x.strip().lower() == "sim" else 0

# ------------------------------
# DEFINIÇÃO DO PESO DA ENTREVISTA
# ------------------------------
interview_weights = {
    "Excelente": 10,
    "Muito Bom": 8,
    "Bom": 6,
    "Regular": 4,
    "Insuficiente": 2
}

# ------------------------------
# FUNÇÃO DE MACHINE LEARNING SIMPLES: COMPUTA ML SCORE
# ------------------------------
def compute_ml_score(row):
    iw = interview_weights.get(row["Entrevista_Menção"].strip(), 0)
    taf = conv(row["TAF"])
    saude = conv(row["Saúde_Apto"])
    instrucao = conv(row["Instrução_Apto"])
    contra = 1 - conv(row.get("Contraindicado?", row.get("2ª Seção", "")))
    obeso = 1 - conv(row["Obeso"])
    score = iw * 1.0 + taf * 0.5 + saude * 0.5 + instrucao * 0.5 + contra * 0.5 + obeso * 0.5
    return score

# ------------------------------
# FUNÇÃO PARA CALCULAR A SITUAÇÃO FINAL
# ------------------------------
def compute_situacao(row):
    contraindicado = row.get("Contraindicado?")
    if contraindicado is None:
        contraindicado = row.get("2ª Seção", "")
    if row["Saúde_Apto"].strip().lower() == "não":
        return "Inapto"
    if row["TAF"].strip().lower() == "não":
        return "Inapto"
    if row["Entrevista_Menção"].strip().lower() == "insuficiente":
        return "Inapto"
    if contraindicado.strip().lower() == "sim":
        return "Inapto"
    if row["Instrução_Apto"].strip().lower() == "não":
        return "Inapto"
    if row["Obeso"].strip().lower() == "sim":
        return "Inapto"
    return "Apto"

# ------------------------------
# FUNÇÃO PARA REORDENAR E RENOMEAR COLUNAS (EXIBIÇÃO)
# ------------------------------
def reordenar_e_renomear(df):
    if "2ª Seção" in df.columns:
        df = df.rename(columns={"2ª Seção": "Contraindicado?"})
    df["Entrevista Peso"] = df["Entrevista_Menção"].apply(lambda x: interview_weights.get(x.strip(), 0))
    df["Situação Calculada"] = df.apply(compute_situacao, axis=1)
    df["ML Score"] = df.apply(compute_ml_score, axis=1)
    nova_ordem = ["Nome", "Saúde_Apto", "Saúde_Motivo", "TAF", "Entrevista_Menção", "Entrevista Peso", "ML Score", "Entrevista_Obs", "Habilidade", "Contraindicado?", "Instrução_Apto", "Obeso", "Situação Calculada"]
    df = df[[col for col in nova_ordem if col in df.columns]]
    return df

# ------------------------------
# FUNÇÃO PARA ORDENAR E NUMERAR REGISTROS (REMOVENDO ML SCORE AO FINAL)
# ------------------------------
def ordenar_e_numerar(df):
    df["sit_status"] = df["Situação Calculada"].map({"Apto": 0, "Inapto": 1})
    df = df.sort_values(by=["sit_status", "ML Score"], ascending=[True, False])
    # Remove as colunas auxiliares antes de exibir:
    df = df.drop(columns=["ML Score", "sit_status"])
    df = df.reset_index(drop=True)
    df.insert(0, "Ordem", df.index + 1)
    return df

# ------------------------------
# FUNÇÕES PARA EXIBIÇÃO DOS CONSCRITOS
# ------------------------------
def exibir_conscritose_status(filtro_pelotao=None):
    all_values = sheet.get_all_values()
    if len(all_values) < 2:
        st.info("Nenhum conscrito cadastrado.")
        return
    headers = all_values[0]
    data = all_values[1:]
    df = pd.DataFrame(data, columns=headers)
    df = reordenar_e_renomear(df)
    if filtro_pelotao == 1:
        df = df[df["Nome"].str[0].str.upper().isin(list("ABCDE"))]
    elif filtro_pelotao == 2:
        df = df[df["Nome"].str[0].str.upper().isin(list("FGHIJ"))]
    df = ordenar_e_numerar(df)
    def color_sit(value):
        if value == "Inapto":
            return "background-color: red; color: white;"
        else:
            return "background-color: lightgreen; color: black;"
    styled_df = df.style.applymap(color_sit, subset=["Situação Calculada"])
    st.dataframe(styled_df)

# ------------------------------
# FUNÇÃO PARA GERAR CSV (RELATÓRIO)
# ------------------------------
def gerar_relatorio_pelotao(pelotao):
    all_values = sheet.get_all_values()
    if len(all_values) < 2:
        st.info("Nenhum conscrito cadastrado.")
        return None
    headers = all_values[0]
    data = all_values[1:]
    df = pd.DataFrame(data, columns=headers)
    if "Nome" not in df.columns:
        st.error("A coluna 'Nome' não foi encontrada. Verifique o cabeçalho da planilha principal.")
        return None
    df = reordenar_e_renomear(df)
    if pelotao == 1:
        df = df[df["Nome"].str[0].str.upper().isin(list("ABCDE"))]
    else:
        df = df[df["Nome"].str[0].str.upper().isin(list("FGHIJ"))]
    df = ordenar_e_numerar(df)
    csv_str = df.to_csv(index=False, encoding="utf-8-sig")
    return csv_str.encode("utf-8-sig")

# ------------------------------
# MENU LATERAL
# ------------------------------
menu_option = st.sidebar.radio("MENU", ["Atualizar Conscrito", "Relatórios"])

if menu_option == "Atualizar Conscrito":
    st.sidebar.markdown("### Selecione o conscrito")
    all_values = sheet.get_all_values()
    if len(all_values) < 2:
        st.info("Nenhum conscrito cadastrado.")
        st.stop()
    header = all_values[0]
    data = all_values[1:]
    names = [row[0] for row in data]
    search_name = st.sidebar.text_input("Pesquisar conscrito:")
    if search_name:
        filtered_names = [name for name in names if search_name.lower() in name.lower()]
    else:
        filtered_names = names
    if filtered_names:
        selected_name = st.sidebar.selectbox("Selecione o conscrito:", filtered_names)
    else:
        st.sidebar.info("Nenhum conscrito encontrado.")
        st.stop()
    row_num = None
    for i, row in enumerate(data):
        if row[0] == selected_name:
            row_num = i + 2
            break
    if row_num is None:
        st.error("Conscrito não encontrado.")
        st.stop()
    st.header(f"Atualizando informações do conscrito: {selected_name}")
    tab_names = ["Saúde", "Teste de Aptidão Física", "Entrevista", "Habilidade", "Contraindicado?", "Equipe de Instrução"]
    tabs = st.tabs(tab_names)
    with tabs[0]:
        st.subheader("⛑️Saúde")
        saude_apto = st.radio("Está apto pela seção de saúde?", ("Sim", "Não"))
        saude_motivo = ""
        if saude_apto == "Não":
            saude_motivo = st.text_input("Qual o motivo?")
        if st.button("🦅Salvar Saúde🦅", key="salvar_saude"):
            sheet.update(f"B{row_num}:C{row_num}", [[saude_apto, saude_motivo]])
            st.success("✅Dados de Saúde atualizados.")
    with tabs[1]:
        st.subheader("🏃‍♂️‍➡️Teste de Aptidão Física (TAF)")
        taf = st.radio("Passou no TAF?", ("Sim", "Não"))
        if st.button("🦅Salvar TAF🦅", key="salvar_taf"):
            sheet.update(f"D{row_num}", [[taf]])
            st.success("🦅Dados do TAF atualizados🦅")
    with tabs[2]:
        st.subheader("Entrevista")
        entrevista_mencao = st.selectbox("Menção", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
        entrevista_obs = st.text_area("Observações do entrevistador")
        if st.button("Salvar Entrevista", key="salvar_entrevista"):
            sheet.update(f"E{row_num}:F{row_num}", [[entrevista_mencao, entrevista_obs]])
            st.success("🦅Dados da Entrevista atualizados.🦅")
    with tabs[3]:
        st.subheader("Habilidade")
        tem_habilidade = st.radio("Tem alguma habilidade?", ("Sim", "Não"))
        habilidade_text = ""
        if tem_habilidade == "Sim":
            habilidade_text = st.text_input("Quais habilidades?")
        valor_habilidade = habilidade_text if tem_habilidade == "Sim" else "Não"
        if st.button("🦅Salvar Habilidade🦅", key="salvar_habilidade"):
            sheet.update(f"G{row_num}", [[valor_habilidade]])
            st.success("Dados de Habilidade atualizados.")
    with tabs[4]:
        st.subheader("Contraindicado?")
        contraindicado = st.radio("É contra indicado?", ("Sim", "Não"))
        if st.button("🦅Salvar Dados?🦅", key="salvar_contra"):
            sheet.update(f"H{row_num}", [[contraindicado]])
            st.success("Dados de Contraindicação atualizados.")
    with tabs[5]:
        st.subheader("Equipe de Instrução")
        instrucao_apto = st.radio("É apto pela equipe de instrução?", ("Sim", "Não"))
        obeso = st.radio("É obeso?", ("Sim", "Não"))
        if st.button("🦅Salvar Equipe de Instrução🦅", key="salvar_instrucao"):
            sheet.update(f"I{row_num}:J{row_num}", [[instrucao_apto, obeso]])
            st.success("Dados da Equipe de Instrução atualizados.")

elif menu_option == "📄Relatórios":
    st.header("Relatórios")
    tab_rel = st.tabs(["Relatório 1º Pelotão", "Relatório 2º Pelotão"])
    with tab_rel[0]:
        st.subheader("Relatório 1º Pelotão")
        exibir_conscritose_status(filtro_pelotao=1)
        csv1 = gerar_relatorio_pelotao(1)
        if csv1:
            st.download_button(label="Baixar CSV 1º Pelotão", data=csv1, file_name="relatorio_1pelotao.csv", mime="text/csv")
    with tab_rel[1]:
        st.subheader("Relatório 2º Pelotão")
        exibir_conscritose_status(filtro_pelotao=2)
        csv2 = gerar_relatorio_pelotao(2)
        if csv2:
            st.download_button(label="Baixar CSV 2º Pelotão", data=csv2, file_name="relatorio_2pelotao.csv", mime="text/csv")

# ------------------------------
# INSERIR NOVO CONSCRITO (apenas o nome)
# ------------------------------
st.markdown("<br><br>", unsafe_allow_html=True)
st.subheader("Inserir Novo Conscrito")
with st.form("form_inserir_novo"):
    novo_nome = st.text_input("Nome completo do conscrito:")
    submitted = st.form_submit_button("Inserir")
    if submitted:
        if not novo_nome:
            st.warning("Preencha o nome!")
        else:
            sheet.append_row([novo_nome, "-", "-", "-", "-", "-", "-", "-", "-"])
            st.success(f"✅Conscrito {novo_nome} inserido com sucesso!")
            st.experimental_rerun()

# ------------------------------
# EXIBIÇÃO COMPLETA DOS CONSCRITOS (SEM FILTRO) – NA PÁGINA PRINCIPAL
# ------------------------------
if menu_option != "Relatórios":
    st.markdown("---")
    st.subheader("Visualização Completa dos Conscritos")
    exibir_conscritose_status()

# ------------------------------
# CUSTOMIZAÇÃO VISUAL: CONTEÚDO PRINCIPAL COM FUNDO PRETO E TEXTO BRANCO; SIDEBAR COM FUNDO CINZA; RODAPÉ NO SIDEBAR COM TEXTO PRETO
# ------------------------------
st.markdown("""
    <style>
    .reportview-container {
        background-color: black;
        color: white;
    }
    h1, h2, h3, h4, h5, h6 {
        color: white;
    }
    /* Sidebar com fundo cinza e texto branco */
    [data-testid="stSidebar"] {
        background-color: gray;
        color: white;
    }
    [data-testid="stSidebar"] * {
        color: white;
    }
    /* Garante que os inputs na sidebar tenham texto preto */
    [data-testid="stSidebar"] input {
        color: black !important;
        background-color: white !important;
    }
    /* Rodapé da sidebar com texto preto */
    .sidebar-footer {
        text-align: center;
        font-size: 10px;
        color: black;
    }
    /* Garante que áreas de tabs tenham fundo preto */
    [data-testid="stHorizontalBlock"] {
        background-color: black !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
    <br><br><br>
    <div class="sidebar-footer">
    Código Python escrito por: CAP TREMMEL - PQDT 90.360<br>
    Qualquer dúvida ou erro do app, entrar em ctt (21) 974407682
    </div>
""", unsafe_allow_html=True)
