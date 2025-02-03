import streamlit as st
import pandas as pd
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import hashlib

# 🔹 Configuração do Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS_JSON')
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# 🔹 Acessando planilhas
sheet = client.open("Relatório de Conscritos").sheet1
users_sheet = client.open("Relatório de Conscritos").worksheet("Usuarios")

# 🔹 Função para hash de senha
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# 🔹 Função para verificar credenciais
def autenticar_usuario(usuario, senha):
    usuarios = users_sheet.get_all_records()
    senha_hash = hash_senha(senha)
    
    for user in usuarios:
        if user['usuario'] == usuario and user['senha'] == senha_hash:
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
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos. Tente novamente.")

# 🔹 Tela Principal (após login)
def main_app():
    st.title("Seleção Complementar 2025 - 2ª CIA TIGRE")

    # 🔹 Inicializando lista de conscritos
    if "conscritos" not in st.session_state:
        st.session_state.conscritos = []

    # 🔹 Peso para menções
    peso_mencao = {
        "Excelente": 10,
        "Muito Bom": 8,
        "Bom": 6,
        "Regular": 4,
        "Insuficiente": 0
    }

    # 🔹 Função para coletar dados dos conscritos
    def coletar_dados():
        st.subheader("Cadastro de Conscritos")
        nome = st.text_input("Nome do conscrito:")
        if not nome:
            st.warning("Por favor, preencha o nome do conscrito.")
            return

        col1, col2 = st.columns(2)
        with col1:
            obeso = st.radio("É obeso?", ("Sim", "Não"))
            passou_saude = st.radio("Passou na saúde?", ("Sim", "Não"))
            passou_teste_fisico = st.radio("Passou no teste físico?", ("Sim", "Não"))
            menção = st.selectbox("Menção na entrevista:", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
            contra_indicado = st.radio("É contra indicado?", ("Sim", "Não"))

        with col2:
            apto_instrucao = st.radio("Apto pela equipe de instrução?", ("Sim", "Não"))
            habilidades = st.number_input("Habilidades (quantidade):", min_value=0, max_value=10)
            habilidades_descricao = st.text_area("Quais habilidades? (Descreva)")

        # Verificação de reprovação
        status = "Apto"
        if obeso == "Sim":
            status = "Inapto - Obesidade"
        elif passou_saude == "Não":
            status = "Inapto - Saúde"
        elif passou_teste_fisico == "Não":
            status = "Inapto - Teste Físico"
        elif contra_indicado == "Sim":
            status = "Inapto - Contraindicado"
        elif apto_instrucao == "Não":
            status = "Inapto - Não Apto pela Instrução"

        habilidades_str = str(habilidades) if habilidades > 0 else "-"
        habilidades_descricao = habilidades_descricao if habilidades > 0 else "-"

        conscritos_existentes = [c[1] for c in st.session_state.conscritos]
        if nome in conscritos_existentes:
            st.warning(f"O conscrito {nome} já foi registrado.")
            return

        gravar = st.button("🦅Gravar🦅")
        if gravar:
            sheet.append_row([nome, menção, habilidades_str, habilidades_descricao, peso_mencao[menção], status])
            st.session_state.conscritos.append((nome, menção, habilidades_str, habilidades_descricao, peso_mencao[menção], status))
            st.success(f"✅ Dados de {nome} salvos com sucesso!")

    coletar_dados()

# 🔹 Executar Login antes do app principal
if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
else:
    main_app()
