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
        # Atualiza a senha para hash, se armazenada em texto puro
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
            st.success(f"Bem-vindo, {usuario}!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Tente novamente.")

if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
    st.stop()

# ------------------------------
# FUNÇÃO PARA CALCULAR A SITUAÇÃO FINAL
# ------------------------------
def compute_situacao(row):
    # row é um dicionário (ou Series) com as colunas da planilha
    if row["Saúde_Apto"].strip().lower() == "não":
        return "Inapto"
    if row["TAF"].strip().lower() == "não":
        return "Inapto"
    if row["Entrevista_Menção"].strip().lower() == "insuficiente":
        return "Inapto"
    if row["2ª Seção"].strip().lower() == "sim":
        return "Inapto"
    if row["Instrução_Apto"].strip().lower() == "não":
        return "Inapto"
    if row["Obeso"].strip().lower() == "sim":
        return "Inapto"
    return "Apto"

# Dicionário para o peso da entrevista
interview_weights = {
    "Excelente": 10,
    "Muito Bom": 8,
    "Bom": 6,
    "Regular": 4,
    "Insuficiente": 2
}

# ------------------------------
# FUNÇÃO PARA REORDENAR E RENOMEAR COLUNAS NA EXIBIÇÃO
# ------------------------------
def reordenar_e_renomear(df):
    # Renomeia "2ª Seção" para "Contraindicado?"
    df = df.rename(columns={"2ª Seção": "Contraindicado?"})
    # Insere a coluna "Entrevista Peso" imediatamente após "Entrevista_Menção"
    # Primeiro, calculamos o peso com base na menção
    df["Entrevista Peso"] = df["Entrevista_Menção"].apply(lambda x: interview_weights.get(x.strip(), 0))
    # Calcula a situação
    df["Situação Calculada"] = df.apply(compute_situacao, axis=1)
    # Define a nova ordem de colunas desejada
    nova_ordem = ["Nome", "Saúde_Apto", "Saúde_Motivo", "TAF", "Entrevista_Menção", "Entrevista Peso", "Entrevista_Obs", "Contraindicado?", "Instrução_Apto", "Obeso", "Situação Calculada"]
    # Se houver colunas extras (caso a planilha tenha outros campos), mantêm-se apenas os definidos
    df = df[[col for col in nova_ordem if col in df.columns]]
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
    # Se for solicitado filtrar por pelotão (pelotao=1 ou 2), filtra pelo primeiro caractere do nome
    if filtro_pelotao == 1:
        df = df[df["Nome"].str[0].str.upper().isin(list("ABCDE"))]
    elif filtro_pelotao == 2:
        df = df[df["Nome"].str[0].str.upper().isin(list("FGHIJ"))]
    # Função para colorir a coluna "Situação Calculada"
    def color_sit(value):
        if value == "Inapto":
            return "background-color: red; color: white;"
        else:
            return "background-color: lightgreen; color: black;"
    styled_df = df.style.applymap(color_sit, subset=["Situação Calculada"])
    st.dataframe(styled_df)

# ------------------------------
# FUNÇÃO PARA GERAR CSV (RELATÓRIO) COM COLUNAS REORDENADAS
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
    # Filtra por pelotão: 1 = A–E, 2 = F–J
    if pelotao == 1:
        df_filtrado = df[df["Nome"].str[0].str.upper().isin(list("ABCDE"))]
    else:
        df_filtrado = df[df["Nome"].str[0].str.upper().isin(list("FGHIJ"))]
    # Retorna o CSV com índice falso
    return df_filtrado.to_csv(index=False).encode('utf-8')

# ------------------------------
# MENU LATERAL: Atualizar Conscrito / Relatórios
# ------------------------------
menu_option = st.sidebar.radio("Menu", ["Atualizar Conscrito", "Relatórios"])

if menu_option == "Atualizar Conscrito":
    # Adiciona uma opção para selecionar entre atualizar um conscrito existente ou inserir um novo
    update_option = st.sidebar.radio("Operação", ["Atualizar Conscrito Existente", "Inserir Novo Conscrito"])
    
    if update_option == "Inserir Novo Conscrito":
        st.header("Inserir Novo Conscrito")
        with st.form("form_novo_conscripto"):
            nome = st.text_input("Nome do conscrito:")
            st.markdown("#### Saúde")
            saude_apto = st.radio("Está apto pela seção de saúde?", ("Sim", "Não"))
            saude_motivo = ""
            if saude_apto == "Não":
                saude_motivo = st.text_input("Qual o motivo?")
            st.markdown("#### Teste de Aptidão Física (TAF)")
            taf = st.radio("Passou no TAF?", ("Sim", "Não"))
            st.markdown("#### Entrevista")
            entrevista_mencao = st.selectbox("Menção", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
            entrevista_obs = st.text_area("Observações do entrevistador")
            st.markdown("#### Contraindicado?")
            contraindicado = st.radio("É contra indicado?", ("Sim", "Não"))
            st.markdown("#### Equipe de Instrução")
            instrucao_apto = st.radio("É apto pela equipe de instrução?", ("Sim", "Não"))
            obeso = st.radio("É obeso?", ("Sim", "Não"))
            submitted = st.form_submit_button("Inserir Conscrito")
            if submitted:
                if not nome:
                    st.warning("Preencha o nome do conscrito!")
                else:
                    # Insere a nova linha com as colunas na ordem:
                    # Nome, Saúde_Apto, Saúde_Motivo, TAF, Entrevista_Menção, Entrevista_Obs, 2ª Seção, Instrução_Apto, Obeso
                    sheet.append_row([nome, saude_apto, saude_motivo, taf, entrevista_mencao, entrevista_obs, contraindicado, instrucao_apto, obeso])
                    st.success(f"Conscrito {nome} inserido com sucesso!")
                    st.experimental_rerun()
    
    else:  # Atualizar Conscrito Existente
        st.header("Atualizar Conscrito Existente")
        all_values = sheet.get_all_values()
        if len(all_values) < 2:
            st.info("Nenhum conscrito cadastrado.")
            st.stop()
        header = all_values[0]
        data = all_values[1:]
        # Considera que a coluna A é o Nome
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
        # Localiza a linha (contando com o cabeçalho)
        row_num = None
        for i, row in enumerate(data):
            if row[0] == selected_name:
                row_num = i + 2
                break
        if row_num is None:
            st.error("Conscrito não encontrado.")
            st.stop()
        st.header(f"Atualizando informações do conscrito: {selected_name}")
        tab_names = ["Saúde", "Teste de Aptidão Física", "Entrevista", "Contraindicado?", "Equipe de Instrução"]
        tabs = st.tabs(tab_names)
        # Aba Saúde
        with tabs[0]:
            st.subheader("Saúde")
            saude_apto = st.radio("Está apto pela seção de saúde?", ("Sim", "Não"))
            saude_motivo = ""
            if saude_apto == "Não":
                saude_motivo = st.text_input("Qual o motivo?")
            if st.button("Salvar Saúde", key="salvar_saude"):
                sheet.update(f"B{row_num}:C{row_num}", [[saude_apto, saude_motivo]])
                st.success("Dados de Saúde atualizados.")
        # Aba TAF
        with tabs[1]:
            st.subheader("Teste de Aptidão Física (TAF)")
            taf = st.radio("Passou no TAF?", ("Sim", "Não"))
            if st.button("Salvar TAF", key="salvar_taf"):
                sheet.update(f"D{row_num}", [[taf]])
                st.success("Dados do TAF atualizados.")
        # Aba Entrevista
        with tabs[2]:
            st.subheader("Entrevista")
            entrevista_mencao = st.selectbox("Menção", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
            entrevista_obs = st.text_area("Observações do entrevistador")
            if st.button("Salvar Entrevista", key="salvar_entrevista"):
                sheet.update(f"E{row_num}:F{row_num}", [[entrevista_mencao, entrevista_obs]])
                st.success("Dados da Entrevista atualizados.")
        # Aba Contraindicado? (antiga 2ª Seção)
        with tabs[3]:
            st.subheader("Contraindicado?")
            contraindicado = st.radio("É contra indicado?", ("Sim", "Não"))
            if st.button("Salvar Contraindicado?", key="salvar_2secao"):
                sheet.update(f"G{row_num}", [[contraindicado]])
                st.success("Dados de Contraindicação atualizados.")
        # Aba Equipe de Instrução
        with tabs[4]:
            st.subheader("Equipe de Instrução")
            instrucao_apto = st.radio("É apto pela equipe de instrução?", ("Sim", "Não"))
            obeso = st.radio("É obeso?", ("Sim", "Não"))
            if st.button("Salvar Equipe de Instrução", key="salvar_instrucao"):
                sheet.update(f"H{row_num}:I{row_num}", [[instrucao_apto, obeso]])
                st.success("Dados da Equipe de Instrução atualizados.")

elif menu_option == "Relatórios":
    st.header("Relatórios")
    # Cria duas abas para os relatórios
    tab_rel = st.tabs(["Relatório 1º Pelotão", "Relatório 2º Pelotão"])
    # Função para gerar o CSV já reordenado
    def gerar_relatorio_pelotao_csv(pelotao):
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
            df_filtrado = df[df["Nome"].str[0].str.upper().isin(list("ABCDE"))]
        else:
            df_filtrado = df[df["Nome"].str[0].str.upper().isin(list("FGHIJ"))]
        return df_filtrado.to_csv(index=False).encode('utf-8')
    
    # Em cada aba de relatório, exibe também a visualização completa filtrada
    with tab_rel[0]:
        st.subheader("Relatório 1º Pelotão")
        exibir_conscritose_status(filtro_pelotao=1)
        csv1 = gerar_relatorio_pelotao_csv(1)
        if csv1:
            st.download_button(label="Baixar CSV 1º Pelotão", data=csv1, file_name="relatorio_1pelotao.csv", mime="text/csv")
    with tab_rel[1]:
        st.subheader("Relatório 2º Pelotão")
        exibir_conscritose_status(filtro_pelotao=2)
        csv2 = gerar_relatorio_pelotao_csv(2)
        if csv2:
            st.download_button(label="Baixar CSV 2º Pelotão", data=csv2, file_name="relatorio_2pelotao.csv", mime="text/csv")

# ------------------------------
# EXIBIÇÃO COMPLETA DOS CONSCRITOS (SEM FILTRO) – APENAS NA PÁGINA PRINCIPAL
# ------------------------------
if menu_option != "Relatórios":
    st.markdown("---")
    st.subheader("Visualização Completa dos Conscritos")
    exibir_conscritose_status()

# ------------------------------
# CUSTOMIZAÇÃO VISUAL E CRÉDITOS
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
    .css-ffhzg2 {
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

st.image('IMG_1118.png', width=60, use_container_width=True)
st.markdown('<h1 style="text-align: center; font-size: 40px; margin-bottom: 5px;">SELEÇÃO COMPLEMENTAR 2025</h1>', unsafe_allow_html=True)
st.markdown('<h2 style="text-align: center; margin-top: 0px; margin-bottom: 30px;">2ª CIA - TIGRE</h2>', unsafe_allow_html=True)
st.markdown("""
    <p style="font-size: 10px; color: white; text-align: center;">
    Código Python feito por CAP TREMMEL - PQDT 90.360 | Qualquer erro, entre em contato: 21 974407682
    </p>
""", unsafe_allow_html=True)
