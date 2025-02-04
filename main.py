import streamlit as st
import pandas as pd
import gspread
import json
import os
import sys
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import hashlib

# 🔹 Configuração do Google Sheets usando a variável de ambiente para as credenciais
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS_JSON')
if not creds_json:
    sys.exit("Erro: A variável de ambiente 'GOOGLE_SHEET_CREDENTIALS_JSON' não está definida.")

creds_dict = json.loads(creds_json)  # Carregar como dicionário JSON
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# 🔹 Acessando as planilhas
# Planilha principal com os dados dos conscritos (aba 1)
sheet = client.open("Relatório de Conscritos").sheet1
# Planilha com os usuários para login (aba "Usuarios")
users_sheet = client.open("Relatório de Conscritos").worksheet("Usuarios")

# 🔹 Funções de autenticação e login

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
            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            users_sheet.append_row([usuario, data_hora])
            st.success(f"Bem-vindo, {usuario}!")
            st.rerun()  # Substituído st.experimental_rerun() por st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Tente novamente.")

# 🔹 Verifica se o usuário está logado. Se não, mostra a tela de login e interrompe a execução.
if "logado" not in st.session_state or not st.session_state["logado"]:
    login()
    st.stop()

# 🔹 Inicializando a lista de conscritos no estado da sessão
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

# 🔹 Função para coletar dados de cada conscrito
def coletar_dados():
    st.subheader("Cadastro de Conscritos")
    nome = st.text_input("Nome do conscrito:")
    if not nome:
        st.warning("Por favor, preencha o nome do conscrito.")
        return

    # Perguntas em layout de colunas
    col1, col2 = st.columns(2)
    with col1:
        obeso = st.radio("É obeso?", ("Sim", "Não"))
        passou_saude = st.radio("Passou na saúde?⛑️", ("Sim", "Não"))
        passou_teste_fisico = st.radio("Passou no teste físico?🏃‍♂️‍➡️", ("Sim", "Não"))
        menção = st.selectbox("Menção na entrevista:", ["Excelente", "Muito Bom", "Bom", "Regular", "Insuficiente"])
        contra_indicado = st.radio("É contra indicado?🚨", ("Sim", "Não"))
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

    # Se o conscrito não tiver habilidades, colocar "-"
    habilidades_str = str(habilidades) if habilidades > 0 else "-"
    habilidades_descricao = habilidades_descricao if habilidades > 0 else "-"

    # Verificar se o conscrito já foi registrado para evitar duplicações
    conscritos_existentes = [c[0] for c in st.session_state.conscritos]
    if nome in conscritos_existentes:
        st.warning(f"O conscrito {nome} já foi registrado.")
        return

    # Criar botão "Gravar"
    gravar = st.button("🦅Gravar🦅")

    if gravar:
        # Salvar no Google Sheets com 6 colunas
        sheet.append_row([nome, menção, habilidades_str, habilidades_descricao, peso_mencao[menção], status])
        # Atualizar a lista de conscritos na sessão
        st.session_state.conscritos.append((nome, menção, habilidades_str, habilidades_descricao, peso_mencao[menção], status))
        st.success(f"✅ Dados de {nome} salvos com sucesso!")

# 🔹 Função para exibir os conscritos organizados por pelotão
def exibir_conscritos():
    # Buscar os dados salvos no Google Sheets (ignorando cabeçalho)
    conscritos = sheet.get_all_values()[1:]

    # Ordenar conscritos: primeiro pela menção (peso), depois pelo status (Apto/Inapto) e, por fim, por ordem alfabética
    conscritos_ordenados = sorted(conscritos, key=lambda x: (
        peso_mencao.get(x[1], 0),
        x[5] == "Apto",
        x[0]
    ), reverse=True)
    pelotao_1 = [c for c in conscritos_ordenados if c[0][0].upper() in "ABCDE"]
    pelotao_2 = [c for c in conscritos_ordenados if c[0][0].upper() in "FGHIJ"]

    colunas = ["Nome", "Menção", "Habilidades", "Quais Habilidades", "Peso da Menção", "Situação"]

    # Exibir a tabela do 1º Pelotão
    st.subheader("1º Pelotão (A a E)")
    pelotao_1_df = pd.DataFrame(pelotao_1, columns=colunas)
    pelotao_1_df['Situação'] = pelotao_1_df['Situação'].apply(lambda x: "Inapto" if "Inapto" in x else "Apto")
    st.table(pelotao_1_df.style.apply(
        lambda x: ['background-color: lightcoral' if 'Inapto' in v else 'background-color: lightgreen' if 'Apto' in v else '' for v in x], 
        axis=1
    ))

    # Exibir a tabela do 2º Pelotão
    st.subheader("2º Pelotão (F a J)")
    pelotao_2_df = pd.DataFrame(pelotao_2, columns=colunas)
    pelotao_2_df['Situação'] = pelotao_2_df['Situação'].apply(lambda x: "Inapto" if "Inapto" in x else "Apto")
    st.table(pelotao_2_df.style.apply(
        lambda x: ['background-color: lightcoral' if 'Inapto' in v else 'background-color: lightgreen' if 'Apto' in v else '' for v in x], 
        axis=1
    ))

# 🔹 Função para gerar relatório CSV (Excel)
def gerar_relatorio_pelotao(pelotao):
    conscritos = sheet.get_all_values()[1:]
    colunas = ["Nome", "Menção", "Habilidades", "Quais Habilidades", "Peso da Menção", "Situação"]

    conscritos_ordenados = sorted(conscritos, key=lambda x: (
        peso_mencao.get(x[1], 0),
        x[5] == "Apto",
        x[0]
    ), reverse=True)

    if pelotao == 1:
        conscritos_filtrados = [c for c in conscritos_ordenados if c[0][0].upper() in "ABCDE"]
    else:
        conscritos_filtrados = [c for c in conscritos_ordenados if c[0][0].upper() in "FGHIJ"]

    df = pd.DataFrame(conscritos_filtrados, columns=colunas)
    excel_file = df.to_csv(index=False).encode('utf-8')
    return excel_file

# 🔹 Interface Streamlit - Customização visual
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

# Seção de cadastro e exibição dos conscritos
coletar_dados()
exibir_conscritos()

# Botões para gerar relatório (CSV)
st.subheader("Gerar Relatório")
st.download_button(label="Baixar Relatório (1º Pelotão)", data=gerar_relatorio_pelotao(1), file_name="relatorio_1pelotao.csv", mime="text/csv")
st.download_button(label="Baixar Relatório (2º Pelotão)", data=gerar_relatorio_pelotao(2), file_name="relatorio_2pelotao.csv", mime="text/csv")

# Créditos
st.markdown("""
    <p style="font-size: 10px; color: white; text-align: center;">Código Python feito por CAP TREMMEL - PQDT 90.360</p>
    <p style="font-size: 10px; color: white; text-align: center;">Qualquer erro, entre em contato: 21 974407682</p>
""", unsafe_allow_html=True)
