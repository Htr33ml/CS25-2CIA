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
        # Atualiza a senha para hash, se estiver armazenada em texto puro
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
            # Obtém a data/hora conforme o horário de Brasília
            data_hora = datetime.now(brasilia_tz).strftime("%Y-%m-%d %H:%M:%S")
            # Registra o login na aba "Logins"
            logins_sheet.append_row([usuario, data_hora])
            st.success(f"Bem-vindo, {usuario}!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Tente novamente.")

# ------------------------------
# CHECAGEM DE LOGIN
# ------------------------------
if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
    st.stop()

# ------------------------------
# VARIÁVEIS GLOBAIS
# ------------------------------
# Caso queira usar a lista de conscritos na sessão (opcional)
if "conscritos" not in st.session_state:
    st.session_state.conscritos = []

# Dicionário com o peso da menção (usado para cálculo automático)
peso_mencao = {
    "Excelente": 10,
    "Muito Bom": 8,
    "Bom": 6,
    "Regular": 4,
    "Insuficiente": 0
}

# ------------------------------
# PÁGINA DE CADASTRO (INSERÇÃO)
# ------------------------------
def cadastro_page():
    st.header("Cadastro de Conscritos")
    
    st.markdown("### Cadastro Individual")
    with st.form("form_cadastro_individual"):
        nome = st.text_input("Nome do conscrito:")
        menção = st.selectbox("Menção na entrevista:", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
        habilidades = st.number_input("Habilidades (quantidade):", min_value=0, max_value=10, step=1)
        habilidades_descricao = st.text_area("Quais habilidades? (Descreva)")
        status = st.selectbox("Situação:", [
            "Apto", 
            "Inapto - Obesidade", 
            "Inapto - Saúde", 
            "Inapto - Teste Físico", 
            "Inapto - Contraindicado", 
            "Inapto - Não Apto"
        ])
        submitted = st.form_submit_button("Cadastrar Conscrito")
        if submitted:
            if not nome:
                st.warning("Preencha o nome do conscrito!")
            else:
                peso = peso_mencao.get(menção, 0)
                sheet.append_row([
                    nome, 
                    menção, 
                    str(habilidades) if habilidades > 0 else "-", 
                    habilidades_descricao if habilidades > 0 else "-", 
                    peso, 
                    status
                ])
                st.success(f"Conscrito {nome} cadastrado com sucesso!")
    
    st.markdown("---")
    st.markdown("### Cadastro em Lote (CSV)")
    file = st.file_uploader("Carregar arquivo CSV", type=["csv"])
    if file is not None:
        try:
            df = pd.read_csv(file)
            # Verifica se as colunas necessárias existem
            colunas_esperadas = {"Nome", "Menção", "Habilidades", "Quais Habilidades", "Situação"}
            if not colunas_esperadas.issubset(set(df.columns)):
                st.error("O arquivo CSV não possui as colunas necessárias. Verifique se contém: Nome, Menção, Habilidades, Quais Habilidades, Situação.")
            else:
                cont = 0
                for _, row in df.iterrows():
                    nome = row["Nome"]
                    menção = row["Menção"]
                    habilidades = row["Habilidades"]
                    habilidades_descricao = row["Quais Habilidades"]
                    status = row["Situação"]
                    peso = peso_mencao.get(menção, 0)
                    sheet.append_row([
                        nome, 
                        menção, 
                        str(habilidades) if pd.notna(habilidades) and habilidades > 0 else "-", 
                        habilidades_descricao if pd.notna(habilidades_descricao) else "-", 
                        peso, 
                        status
                    ])
                    cont += 1
                st.success(f"{cont} conscritos cadastrados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

# ------------------------------
# PÁGINA DE ADMINISTRAÇÃO (EDIÇÃO)
# ------------------------------
def administracao_page():
    st.header("Painel Administrativo de Conscritos")
    data = sheet.get_all_values()
    if len(data) <= 1:
        st.info("Nenhum conscrito cadastrado.")
        return
    # Cria um DataFrame a partir dos dados (pulando o cabeçalho)
    df = pd.DataFrame(data[1:], columns=data[0])
    # Cria uma lista de opções para selecionar o conscrito (exibindo o número da linha e o nome)
    options = [f"{i+2} - {row['Nome']}" for i, row in df.iterrows()]
    selected = st.selectbox("Selecione o conscrito para editar:", options)
    # Obtém o número da linha no Google Sheets (considerando que a linha 1 é o cabeçalho)
    row_num = int(selected.split(" - ")[0])
    # Como o DataFrame df foi criado a partir de data[1:], o índice do conscrito é (row_num - 2)
    row_data = df.iloc[row_num - 2]
    
    st.markdown("### Editar Conscrito")
    with st.form("form_edicao"):
        novo_nome = st.text_input("Nome", value=row_data["Nome"])
        novo_menção = st.selectbox("Menção", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"], 
                                   index=["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"].index(row_data["Menção"]))
        # Tenta converter o valor atual de habilidades para inteiro (se possível)
        try:
            current_habilidades = int(row_data["Habilidades"]) if row_data["Habilidades"].isdigit() else 0
        except Exception:
            current_habilidades = 0
        novo_habilidades = st.number_input("Habilidades (quantidade)", min_value=0, max_value=10, step=1, value=current_habilidades)
        novo_hab_desc = st.text_area("Quais Habilidades", value=row_data["Quais Habilidades"])
        novo_status = st.selectbox("Situação", [
            "Apto", 
            "Inapto - Obesidade", 
            "Inapto - Saúde", 
            "Inapto - Teste Físico", 
            "Inapto - Contraindicado", 
            "Inapto - Não Apto"
        ], index=["Apto", "Inapto - Obesidade", "Inapto - Saúde", "Inapto - Teste Físico", "Inapto - Contraindicado", "Inapto - Não Apto"].index(row_data["Situação"]))
        submit_edicao = st.form_submit_button("Salvar Alterações")
        if submit_edicao:
            novo_peso = peso_mencao.get(novo_menção, 0)
            # Atualiza a linha correspondente na planilha (colunas A a F)
            new_values = [[novo_nome, novo_menção, str(novo_habilidades) if novo_habilidades > 0 else "-", 
                           novo_hab_desc if novo_hab_desc else "-", novo_peso, novo_status]]
            sheet.update(f"A{row_num}:F{row_num}", new_values)
            st.success("Registro atualizado com sucesso!")
            st.experimental_rerun()

    st.markdown("---")
    st.markdown("### Visualização Completa dos Conscritos")
    st.dataframe(df)

# ------------------------------
# INTERFACE PRINCIPAL: BARRA LATERAL
# ------------------------------
st.sidebar.title("Menu Administrativo")
modo = st.sidebar.radio("Selecione a opção desejada:", ["Cadastro", "Administração"])

if modo == "Cadastro":
    cadastro_page()
else:
    administracao_page()

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
