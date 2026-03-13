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
    # Se você vir este erro no log do Render, verifique a aba Environment Variables!
    print("⚠️ A variável GROQ_API_KEY não foi configurada.")

client = OpenAI(
    api_key=api_key if api_key else "dummy_key", 
    base_url="https://api.groq.com/openai/v1"
)

# ==========================================
# MOTOR DE KEEP-ALIVE E PÁGINA INICIAL
# ==========================================
@app.route("/")
def home():
    return "<h1>🤖 Bot Financeiro da Kaliba está ONLINE!</h1><p>O servidor está rodando perfeitamente.</p>", 200

@app.route("/ping")
def ping():
    return "Bot acordado!", 200

def ping_automatico():
    # Espera o servidor subir totalmente antes de começar
    time.sleep(30)
    url_ping = "https://meu-bot-financeiro-vcou.onrender.com/ping"
    while True:
        try:
            requests.get(url_ping)
            print("🟢 Ping de auto-sustentação enviado.")
        except:
            pass
        time.sleep(600) # 10 minutos

threading.Thread(target=ping_automatico, daemon=True).start()

# ==========================================
# 2. Banco de Dados
# ==========================================
def conectar_banco():
    conn = sqlite3.connect('gastos_kaliba.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            categoria TEXT,
            valor REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    return conn

def obter_historico(cursor):
    cursor.execute("SELECT role, content FROM historico ORDER BY id DESC LIMIT 20")
    linhas = cursor.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(linhas)]

def salvar_historico(cursor, conn, role, content):
    cursor.execute("INSERT INTO historico (role, content) VALUES (?, ?)", (role, content))
    conn.commit()

# ==========================================
# 3. Inteligência Artificial
# ==========================================
def extrair_dados_da_mensagem(mensagem_usuario, historico_conversa):
    meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
    mes_atual_nome = meses_pt[datetime.now().strftime("%m")]
    ano_atual = datetime.now().strftime("%Y")
    
    prompt_sistema = f"""O SEU NOME é Kaliba. Você é uma assistente financeira pessoal brilhante.
    O nome do usuário é Hector. Hoje é {datetime.now().strftime('%d/%m/%Y')}.
    
    Você DEVE retornar APENAS um objeto JSON válido:
    {{
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta humana aqui.",
        "transacoes": []
    }}
    """
    
    mensagens_para_ia = [{"role": "system", "content": prompt_sistema}]
    mensagens_para_ia.extend(historico_conversa)
    mensagens_para_ia.append({"role": "user", "content": mensagem_usuario})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Modelo ultra rápido para evitar timeout do Twilio
            response_format={ "type": "json_object" },
            messages=mensagens_para_ia
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return f"ERRO_TECNICO: {str(e)}"

# ==========================================
# 4. Conexão com WhatsApp (Ajustada)
# ==========================================
@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp():
    # Se alguém acessar pelo navegador (GET), damos um aviso amigável
    if request.method == 'GET':
        return "O endpoint /whatsapp está ativo e aguardando mensagens POST do Twilio!", 200

    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    # Comando de Reset
    if any(palavra in mensagem_usuario for palavra in ["limpar tudo", "resetar", "limpar chat"]):
        cursor.execute("DELETE FROM gastos")
        cursor.execute("DELETE FROM historico")
        conn.commit()
        conn.close()
        resp.message("✅ Kaliba: Memória e gastos zerados!")
        return str(resp)

    # Processamento Normal
    historico = obter_historico(cursor)
    dados = extrair_dados_da_mensagem(mensagem_usuario, historico)

    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Kaliba: Tive um problema técnico: {dados}")
        conn.close()
        return str(resp)

    try:
        resposta_da_ia = dados.get("resposta_ia", "Estou processando...")
        transacoes = dados.get("transacoes", [])
        
        salvar_historico(cursor, conn, "user", mensagem_usuario)
        salvar_historico(cursor, conn, "assistant", resposta_da_ia)
        
        if not transacoes:
            resp.message(f"🤖 {resposta_da_ia}")
        else:
            data_atual = datetime.now().strftime("%Y-%m-%d")
            for item in transacoes:
                categoria = str(item.get('categoria', 'Geral')).capitalize()
                valor = abs(float(str(item.get('valor', 0)).replace(",", ".")))
                tipo = str(item.get('tipo', 'gasto')).lower()
                valor_banco = -valor if tipo in ['ganho', 'receita'] else valor
                cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', (data_atual, categoria, valor_banco))
            
            conn.commit()
            resp.message(f"🤖 {resposta_da_ia}\n\n✅ Gasto registrado!")
            
    except Exception as e:
        resp.message(f"❌ Erro ao salvar: {e}")

    conn.close()
    return str(resp)

# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)