import streamlit as st
import pandas as pd
import gspread
import json
import os
import sys
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import hashlib

# Verificar se Streamlit está instalado
try:
    import streamlit as st
except ModuleNotFoundError:
    sys.exit("Erro: O módulo 'streamlit' não está instalado. Execute 'pip install streamlit' para instalá-lo.")

# 🔹 Configuração do Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS_JSON')
if not creds_json:
    sys.exit("Erro: A variável de ambiente 'GOOGLE_SHEET_CREDENTIALS_JSON' não está definida.")

creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# 🔹 Acessando planilhas
try:
    sheet = client.open("Relatório de Conscritos").sheet1
    users_sheet = client.open("Relatório de Conscritos").worksheet("Usuarios")
except gspread.exceptions.SpreadsheetNotFound:
    sys.exit("Erro: Planilha 'Relatório de Conscritos' não encontrada. Verifique se o nome está correto.")

# 🔹 Função para hash de senha
def hash_senha(senha):
    return hashlib.sha256(senha.strip().encode()).hexdigest()

# 🔹 Função para autenticar o usuário e atualizar a senha caso esteja em texto puro
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

# 🔹 Tela de Login
def login():
    st.title("Login - Seleção Complementar 2025")
    usuario = st.text_input("Usuário:")
    senha = st.text_input("Senha:", type="password")
    if st.button("Entrar"):
        if autenticar_usuario(usuario, senha):
            st.session_state['usuario'] = usuario
            st.session_state['logado'] = True
            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            users_sheet.append_row([usuario, data_hora])
            st.success(f"Bem-vindo, {usuario}!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Tente novamente.")

# 🔹 Interface Streamlit
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

if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
else:
    coletar_dados()
    exibir_conscritos()
    st.subheader("Gerar Relatório")
    st.download_button(label="Baixar Relatório (1º Pelotão)", data=gerar_relatorio_pelotao(1), file_name="relatorio_1pelotao.csv", mime="text/csv")
    st.download_button(label="Baixar Relatório (2º Pelotão)", data=gerar_relatorio_pelotao(2), file_name="relatorio_2pelotao.csv", mime="text/csv")
    st.markdown("""
        <p style="font-size: 10px; color: white; text-align: center;">Código Python feito por CAP TREMMEL - PQDT 90.360</p>
        <p style="font-size: 10px; color: white; text-align: center;">Qualquer erro, entre em contato: 21 974407682</p>
    """, unsafe_allow_html=True)
