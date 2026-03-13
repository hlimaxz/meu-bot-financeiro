import os
import json
import sqlite3
import threading
import time
import requests
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = Flask(__name__)

# 1. Configuração da IA
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("⚠️ A variável GROQ_API_KEY não foi configurada no Render.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

# ==========================================
# MOTOR DE KEEP-ALIVE
# ==========================================
URL_DO_BOT = "https://meu-bot-financeiro-vcou.onrender.com/ping"

@app.route("/ping")
def ping():
    return "Bot acordado e operando!", 200

def ping_automatico():
    while True:
        time.sleep(600)
        try:
            requests.get(URL_DO_BOT)
        except Exception as e:
            pass

threading.Thread(target=ping_automatico, daemon=True).start()
# ==========================================

# 2. Banco de Dados MULTI-CONTAS
def conectar_banco():
    conn = sqlite3.connect('gastos_kaliba.db')
    cursor = conn.cursor()
    
    # Tabela de gastos agora tem a coluna "telefone" para separar os usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefone TEXT,
            data TEXT,
            categoria TEXT,
            valor REAL
        )
    ''')
    
    # Memória agora também é separada por telefone
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefone TEXT,
            role TEXT,
            content TEXT
        )
    ''')
    
    # Atualiza o banco de dados antigo sem quebrar o que já existe
    try:
        cursor.execute("ALTER TABLE gastos ADD COLUMN telefone TEXT DEFAULT 'geral'")
        cursor.execute("ALTER TABLE historico ADD COLUMN telefone TEXT DEFAULT 'geral'")
    except:
        pass
        
    conn.commit()
    return conn

# Funções de Memória Individuais
def obter_historico(cursor, telefone):
    # Puxa apenas a memória atrelada ao número de quem mandou a mensagem
    cursor.execute("SELECT role, content FROM historico WHERE telefone = ? ORDER BY id DESC LIMIT 20", (telefone,))
    linhas = cursor.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(linhas)]

def salvar_historico(cursor, conn, telefone, role, content):
    cursor.execute("INSERT INTO historico (telefone, role, content) VALUES (?, ?, ?)", (telefone, role, content))
    conn.commit()

# 3. Inteligência Artificial
def extrair_dados_da_mensagem(mensagem_usuario, historico_conversa, telefone):
    meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
    mes_atual_nome = meses_pt[datetime.now().strftime("%m")]
    ano_atual = datetime.now().strftime("%Y")
    
    prompt_sistema = f"""O SEU NOME é Kaliba. Você é uma assistente financeira pessoal brilhante em formato de IA.
    Hoje é {datetime.now().strftime('%d/%m/%Y')} (Mês de {mes_atual_nome} de {ano_atual}).
    
    IMPORTANTE: Você agora atende várias pessoas diferentes da mesma família. Cada pessoa tem um banco de dados separado.
    O número de WhatsApp da pessoa que está falando com você agora é: {telefone}. 
    Se você ainda não souber o nome dela, pergunte educadamente. Se já souber pelo histórico, use o nome dela com carinho.
    
    Sua personalidade: Empática, extremamente lógica, analítica e focada em resolver os problemas do usuário.
    
    REGRAS DE OURO PARA LÓGICA E MEMÓRIA:
    1. Leia TODO o histórico da conversa com atenção. Lembre-se do nome do usuário e de seus ganhos.
    2. Se o usuário corrigir um valor, descarte o antigo e refaça a lógica com a nova informação imediatamente.
    3. Pense passo a passo e seja clara nos cálculos.
    
    Você DEVE retornar APENAS um objeto JSON válido, com esta estrutura exata:
    {{
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta humana, natural e muito inteligente.",
        "transacoes": [
            {{"categoria": "Nome Curto", "valor": 0.0, "tipo": "gasto" ou "ganho"}}
        ]
    }}
    """
    
    mensagens_para_ia = [{"role": "system", "content": prompt_sistema}]
    mensagens_para_ia.extend(historico_conversa)
    mensagens_para_ia.append({"role": "user", "content": f"Mensagem do usuário: '{mensagem_usuario}'"})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_format={ "type": "json_object" },
            messages=mensagens_para_ia
        )
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return f"ERRO_TECNICO: {str(e)}"

# 4. Conexão com WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    
    # AQUI ESTÁ A CHAVE DE OURO: O BOT PEGA O NÚMERO DE QUEM MANDOU A MENSAGEM
    numero_remetente = request.values.get('From', 'desconhecido') 
    
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    # O "limpar tudo" agora limpa apenas o banco de dados do número específico
    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario or "limpar chat" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos WHERE telefone = ?", (numero_remetente,))
        cursor.execute("DELETE FROM historico WHERE telefone = ?", (numero_remetente,))
        conn.commit()
        conn.close()
        resp.message("✅ Suas contas e minha memória foram zeradas com sucesso!")
        return str(resp)

    historico = obter_historico(cursor, numero_remetente)
    dados = extrair_dados_da_mensagem(mensagem_usuario, historico, numero_remetente)

    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Ops, o motor travou:\n\n{dados}")
        conn.close()
        return str(resp)

    try:
        intencao = dados.get("intencao", "conversa")
        resposta_da_ia = dados.get("resposta_ia", "")
        transacoes = dados.get("transacoes", [])
        
        salvar_historico(cursor, conn, numero_remetente, "user", mensagem_usuario)
        salvar_historico(cursor, conn, numero_remetente, "assistant", resposta_da_ia)
        
        if intencao == "conversa" or not transacoes:
            resp.message(f"🤖 {resposta_da_ia}")
            
        else:
            data_atual = datetime.now().strftime("%Y-%m-%d")
            
            for item in transacoes:
                categoria = str(item.get('categoria', 'Geral')).capitalize()
                valor_str = str(item.get('valor', 0)).replace(",", ".")
                valor_absoluto = abs(float(valor_str))
                tipo = str(item.get('tipo', 'gasto')).lower()
                
                if tipo == 'ganho' or tipo == 'receita':
                    valor_banco = -valor_absoluto
                else:
                    valor_banco = valor_absoluto
                    
                # Salva a transação amarrada ao número de telefone!
                cursor.execute('INSERT INTO gastos (telefone, data, categoria, valor) VALUES (?, ?, ?, ?)', (numero_remetente, data_atual, categoria, valor_banco))
            
            conn.commit()
            
            mes_atual = datetime.now().strftime("%Y-%m")
            # Puxa o extrato filtrando apenas pelos gastos desse número de telefone
            cursor.execute('SELECT categoria, valor FROM gastos WHERE data LIKE ? AND telefone = ?', (f'{mes_atual}%', numero_remetente))
            registros = cursor.fetchall()
            
            meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
            nome_mes = meses_pt[datetime.now().strftime("%m")]
            
            extrato_txt = f"🗓️ Agenda Mês: {nome_mes}\n✅ Movimentações:\n"
            total = 0.0
            
            for cat, val in registros:
                total += val
                cat_formatada = cat.lower()
                val_formatado = f"{abs(val):.2f}".replace(".", ",")
                
                if val < 0:
                    extrato_txt += f"🟢 + {cat_formatada}: R$ {val_formatado}\n"
                else:
                    extrato_txt += f"🔴 - {cat_formatada}: R$ {val_formatado}\n"
            
            total_formatado = f"{total:.2f}".replace(".", ",")
            
            if total > 0:
                extrato_txt += f"\n📊 Saldo Atual = 🔴 R$ -{total_formatado} (Gastando mais do que ganha)"
            else:
                extrato_txt += f"\n📊 Saldo Atual = 🟢 R$ {str(total_formatado).replace('-', '')} (No azul!)"
            
            mensagem_final = f"🤖 {resposta_da_ia}\n\n{extrato_txt}"
            resp.message(mensagem_final)
            
    except Exception as e:
        resp.message(f"Erro interno ao processar os dados: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)