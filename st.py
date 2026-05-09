# app.py – Sistema Positivo Service
# Execute com: streamlit run app.py

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# -------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA (deve ser o primeiro comando Streamlit)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Positivo Service",
    page_icon="🔧",
    layout="wide"
)

# -------------------------------------------------------------------
# INICIALIZAÇÃO DO BANCO DE DADOS E PASTA DE IMAGENS
# -------------------------------------------------------------------
def init_database():
    """Cria as tabelas e a pasta de imagens se não existirem."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Tabela principal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS formularios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oss TEXT NOT NULL,
            equipamento TEXT,
            ampers_placa TEXT,
            modelo_motor TEXT,
            descricao TEXT,
            rebobinar INTEGER,   -- 0=Não, 1=Sim
            data_criacao TEXT,
            data_modificacao TEXT
        )
    ''')

    # Tabela de peças
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pecas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formulario_id INTEGER,
            nome_peca TEXT,
            FOREIGN KEY (formulario_id) REFERENCES formularios(id) ON DELETE CASCADE
        )
    ''')

    # Tabela de fotos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formulario_id INTEGER,
            caminho TEXT,
            FOREIGN KEY (formulario_id) REFERENCES formularios(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

    # Criar pasta de imagens se não existir
    if not os.path.exists("imagens"):
        os.makedirs("imagens")

init_database()

# -------------------------------------------------------------------
# FUNÇÕES DE MANIPULAÇÃO DO BANCO E ARQUIVOS
# -------------------------------------------------------------------
def salvar_formulario(oss, equipamento, ampers, modelo_motor, descricao, rebobinar, pecas_lista, fotos_lista):
    """Insere novo formulário + peças + fotos."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT INTO formularios 
        (oss, equipamento, ampers_placa, modelo_motor, descricao, rebobinar, data_criacao, data_modificacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (oss, equipamento, ampers, modelo_motor, descricao, rebobinar, data_atual, data_atual))
    form_id = cursor.lastrowid

    for peca in pecas_lista:
        if peca.strip():
            cursor.execute('INSERT INTO pecas (formulario_id, nome_peca) VALUES (?, ?)', (form_id, peca.strip()))

    for foto_bytes in fotos_lista:
        if foto_bytes is not None:
            nome_arq = f"form_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            caminho = os.path.join("imagens", nome_arq)
            with open(caminho, "wb") as f:
                f.write(foto_bytes.getvalue())
            cursor.execute('INSERT INTO fotos (formulario_id, caminho) VALUES (?, ?)', (form_id, caminho))

    conn.commit()
    conn.close()
    return form_id

def atualizar_formulario(form_id, oss, equipamento, ampers, modelo_motor, descricao, rebobinar, pecas_lista, novas_fotos_lista):
    """Atualiza dados e peças; adiciona novas fotos (preserva as antigas)."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    data_mod = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        UPDATE formularios
        SET oss=?, equipamento=?, ampers_placa=?, modelo_motor=?, descricao=?, rebobinar=?, data_modificacao=?
        WHERE id=?
    ''', (oss, equipamento, ampers, modelo_motor, descricao, rebobinar, data_mod, form_id))

    # Substituir lista de peças
    cursor.execute('DELETE FROM pecas WHERE formulario_id=?', (form_id,))
    for peca in pecas_lista:
        if peca.strip():
            cursor.execute('INSERT INTO pecas (formulario_id, nome_peca) VALUES (?, ?)', (form_id, peca.strip()))

    # Adicionar novas fotos
    for foto_bytes in novas_fotos_lista:
        if foto_bytes is not None:
            nome_arq = f"form_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            caminho = os.path.join("imagens", nome_arq)
            with open(caminho, "wb") as f:
                f.write(foto_bytes.getvalue())
            cursor.execute('INSERT INTO fotos (formulario_id, caminho) VALUES (?, ?)', (form_id, caminho))

    conn.commit()
    conn.close()

def deletar_formulario(form_id):
    """Apaga formulário e suas fotos da pasta."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT caminho FROM fotos WHERE formulario_id=?', (form_id,))
    fotos = cursor.fetchall()
    for foto in fotos:
        if os.path.exists(foto[0]):
            os.remove(foto[0])
    cursor.execute('DELETE FROM formularios WHERE id=?', (form_id,))
    conn.commit()
    conn.close()

def carregar_todos_formularios():
    """Retorna DataFrame com todos os formulários + quantidade de fotos."""
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query('SELECT id, oss, equipamento, modelo_motor, data_criacao, rebobinar FROM formularios', conn)
    cursor = conn.cursor()
    qtde = []
    for fid in df['id']:
        cursor.execute('SELECT COUNT(*) FROM fotos WHERE formulario_id=?', (fid,))
        qtde.append(cursor.fetchone()[0])
    df['qtde_fotos'] = qtde
    conn.close()
    return df

def carregar_formulario_para_edicao(form_id):
    """Retorna dicionário com dados do formulário para preencher edição."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT oss, equipamento, ampers_placa, modelo_motor, descricao, rebobinar
        FROM formularios WHERE id=?
    ''', (form_id,))
    dados = cursor.fetchone()
    if not dados:
        return None
    cursor.execute('SELECT nome_peca FROM pecas WHERE formulario_id=?', (form_id,))
    pecas = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {
        'id': form_id,
        'oss': dados[0],
        'equipamento': dados[1],
        'ampers_placa': dados[2],
        'modelo_motor': dados[3],
        'descricao': dados[4],
        'rebobinar': bool(dados[5]),
        'pecas': pecas
    }

def obter_fotos_do_formulario(form_id):
    """Retorna lista de caminhos das fotos."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT caminho FROM fotos WHERE formulario_id=?', (form_id,))
    fotos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return fotos

# -------------------------------------------------------------------
# PÁGINA 1 – HOME COM GRÁFICOS
# -------------------------------------------------------------------
def pagina_home():
    st.image("https://placehold.co/600x150?text=POSITIVO+SERVICE", use_container_width=True)
    st.title("📊 Dashboard Executivo")

    df = carregar_todos_formularios()
    if df.empty:
        st.info("Nenhum formulário cadastrado. Vá para a página de Cadastro.")
        return

    df['data_criacao'] = pd.to_datetime(df['data_criacao'])
    df['mes'] = df['data_criacao'].dt.to_period('M').astype(str)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de OSs", len(df))
    col2.metric("Equipamentos únicos", df['equipamento'].nunique())
    col3.metric("Com fotos", df[df['qtde_fotos'] > 0].shape[0])

    st.subheader("📈 Formulários por Mês")
    contagem_mes = df.groupby('mes').size().reset_index(name='quantidade')
    fig1 = px.bar(contagem_mes, x='mes', y='quantidade', title='Cadastros por Mês')
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("🔄 Necessidade de Rebobinagem")
    df['rebobinar_texto'] = df['rebobinar'].map({1: 'Sim', 0: 'Não'})
    contagem_reb = df['rebobinar_texto'].value_counts().reset_index()
    contagem_reb.columns = ['Rebobinar', 'Quantidade']
    fig2 = px.pie(contagem_reb, values='Quantidade', names='Rebobinar', title='% que vai rebobinar')
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("🏆 Modelos de Motor mais Comuns")
    top_modelos = df['modelo_motor'].value_counts().head(5).reset_index()
    top_modelos.columns = ['Modelo', 'Quantidade']
    fig3 = px.bar(top_modelos, x='Modelo', y='Quantidade', title='Modelos mais usados')
    st.plotly_chart(fig3, use_container_width=True)

# -------------------------------------------------------------------
# PÁGINA 2 – FORMULÁRIO (CADASTRO E EDIÇÃO)
# -------------------------------------------------------------------
def pagina_formulario():
    st.title("📝 Cadastro / Edição")

    # Verifica se estamos editando algum formulário
    if 'editando_id' in st.session_state and st.session_state.editando_id is not None:
        form_id = st.session_state.editando_id
        dados = carregar_formulario_para_edicao(form_id)
        if dados is None:
            st.error("Formulário não encontrado.")
            st.session_state.editando_id = None
            st.rerun()
        st.subheader(f"Editando OS: {dados['oss']}")
        botao_submit = "Atualizar"
    else:
        form_id = None
        dados = None
        botao_submit = "Salvar"

    # Campos do formulário
    oss = st.text_input("OSS *", value=dados['oss'] if dados else "")
    equipamento = st.text_input("Equipamento", value=dados['equipamento'] if dados else "")
    ampers_placa = st.text_input("AMPERS da placa", value=dados['ampers_placa'] if dados else "")
    modelo_motor = st.text_input("Modelo do motor", value=dados['modelo_motor'] if dados else "")
    descricao = st.text_area("Descrição do equipamento", value=dados['descricao'] if dados else "")
    rebobinar = st.checkbox("Vai rebobinar?", value=dados['rebobinar'] if dados else False)

    # Peças
    pecas_default = "\n".join(dados['pecas']) if dados and dados['pecas'] else ""
    pecas_texto = st.text_area("Peças que serão substituídas (uma por linha)", value=pecas_default, height=150)
    lista_pecas = [p.strip() for p in pecas_texto.split("\n") if p.strip()]

    # Captura de fotos (apenas novas, não remove as antigas)
    st.subheader("📸 Adicionar novas fotos")
    if 'fotos_temp' not in st.session_state:
        st.session_state.fotos_temp = []

    foto = st.camera_input("Tirar foto ou escolher imagem")
    if foto:
        st.session_state.fotos_temp.append(foto)

    if st.session_state.fotos_temp:
        st.write(f"📷 **{len(st.session_state.fotos_temp)} foto(s) nova(s) capturada(s)**")
        cols = st.columns(4)
        for idx, img_bytes in enumerate(st.session_state.fotos_temp):
            with cols[idx % 4]:
                st.image(img_bytes, width=100)
        if st.button("🗑️ Limpar fotos não salvas"):
            st.session_state.fotos_temp = []
            st.rerun()

    if st.button(botao_submit, type="primary"):
        if not oss:
            st.error("OSS é obrigatório!")
            return

        if form_id is None:
            # Novo cadastro
            salvar_formulario(oss, equipamento, ampers_placa, modelo_motor, descricao,
                              1 if rebobinar else 0, lista_pecas, st.session_state.fotos_temp)
            st.success("Formulário salvo com sucesso!")
            st.session_state.fotos_temp = []
            st.rerun()
        else:
            # Atualização
            atualizar_formulario(form_id, oss, equipamento, ampers_placa, modelo_motor, descricao,
                                 1 if rebobinar else 0, lista_pecas, st.session_state.fotos_temp)
            st.success("Formulário atualizado!")
            st.session_state.fotos_temp = []
            st.session_state.editando_id = None
            st.rerun()

    if form_id is not None:
        if st.button("Cancelar edição"):
            st.session_state.editando_id = None
            st.rerun()

# -------------------------------------------------------------------
# PÁGINA 3 – CONSULTAR / EDITAR / EXCLUIR
# -------------------------------------------------------------------
def pagina_consulta():
    st.title("🔍 Todos os Formulários")

    df = carregar_todos_formularios()
    if df.empty:
        st.info("Nenhum formulário cadastrado.")
        return

    for idx, row in df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
            col1.write(f"**OSS:** {row['oss']}")
            col2.write(f"**Motor:** {row['modelo_motor']}")
            col3.write(f"**Data:** {row['data_criacao'][:10]}")
            col4.write(f"📸 {row['qtde_fotos']} foto(s)")

            # Botão Editar
            if col5.button("✏️ Editar", key=f"edit_{row['id']}"):
                st.session_state.editando_id = row['id']
                st.session_state.pagina_atual = "Cadastro"
                st.rerun()

            # Botão Excluir (com confirmação dupla)
            if col6.button("🗑️ Excluir", key=f"del_{row['id']}"):
                if st.session_state.get(f"confirm_{row['id']}", False):
                    deletar_formulario(row['id'])
                    st.success(f"Formulário {row['oss']} excluído!")
                    if f"confirm_{row['id']}" in st.session_state:
                        del st.session_state[f"confirm_{row['id']}"]
                    st.rerun()
                else:
                    st.session_state[f"confirm_{row['id']}"] = True
                    st.warning(f"Clique novamente em Excluir para confirmar exclusão de {row['oss']}")

            # Expandir para ver detalhes e fotos
            with st.expander(f"📋 Ver detalhes e fotos - OS {row['oss']}"):
                # Buscar dados completos do formulário (descrição, peças)
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT descricao, ampers_placa FROM formularios WHERE id=?', (row['id'],))
                detalhes = cursor.fetchone()
                cursor.execute('SELECT nome_peca FROM pecas WHERE formulario_id=?', (row['id'],))
                pecas = [p[0] for p in cursor.fetchall()]
                conn.close()

                st.markdown(f"**Descrição:** {detalhes[0]}")
                st.markdown(f"**AMPERS placa:** {detalhes[1]}")
                if pecas:
                    st.markdown("**Peças a substituir:** " + ", ".join(pecas))

                # Exibir fotos existentes
                fotos = obter_fotos_do_formulario(row['id'])
                if fotos:
                    st.markdown("**📸 Fotos salvas:**")
                    cols_fotos = st.columns(4)
                    for i, caminho in enumerate(fotos):
                        if os.path.exists(caminho):
                            with cols_fotos[i % 4]:
                                st.image(caminho, width=150)
                else:
                    st.caption("Nenhuma foto anexada.")
        st.divider()

# -------------------------------------------------------------------
# NAVEGAÇÃO PRINCIPAL (MENU LATERAL)
# -------------------------------------------------------------------
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "Home"
if 'editando_id' not in st.session_state:
    st.session_state.editando_id = None

st.sidebar.title("📋 Menu")
opcao = st.sidebar.radio(
    "Ir para:",
    ["Home", "Cadastro", "Consultar"],
    index=["Home", "Cadastro", "Consultar"].index(st.session_state.pagina_atual)
)
st.session_state.pagina_atual = opcao

if st.session_state.pagina_atual == "Home":
    pagina_home()
elif st.session_state.pagina_atual == "Cadastro":
    pagina_formulario()
else:
    pagina_consulta()