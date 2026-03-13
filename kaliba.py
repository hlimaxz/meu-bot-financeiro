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
# MOTOR DE KEEP-ALIVE (O Despertador Interno)
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
            print("Ping interno enviado com sucesso!")
        except Exception as e:
            print(f"Erro no ping interno: {e}")

threading.Thread(target=ping_automatico, daemon=True).start()
# ==========================================

# 2. Banco de Dados
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
    conn.commit()
    return conn

# 3. Inteligência Artificial MODO ASSISTENTE PESSOAL (SUPER CÉREBRO)
def extrair_dados_da_mensagem(mensagem_usuario):
    prompt_sistema = """Você é uma assistente financeira pessoal inteligente e muito amigável, exclusiva do seu criador, Kaliba.
    Seu objetivo é conversar de forma natural, dar dicas financeiras se ele pedir, e registrar gastos/ganhos perfeitamente.
    
    Você DEVE retornar APENAS um objeto JSON válido, com esta estrutura exata:
    {
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta conversacional, amigável e direta para o Kaliba.",
        "transacao": {"categoria": "Nome Curto", "valor": 0.0, "tipo": "gasto" ou "ganho"} 
    }
    
    Regras vitais:
    1. Se ele relatar uma compra, pagamento ou dinheiro recebido, a intenção é "transacao". Preencha os dados e crie uma resposta confirmando.
    2. Se ele disser "oi", pedir um conselho financeiro, ou fizer uma pergunta, a intenção é "conversa". Crie sua resposta e deixe "transacao" como null.
    3. Seja prestativa, mas não escreva textos gigantes.
    """
    
    prompt_usuario = f"Mensagem do Kaliba: '{mensagem_usuario}'"
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ]
        )
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return f"ERRO_TECNICO: {str(e)}"

# 4. Conexão com WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario or "limpar chat" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos")
        conn.commit()
        conn.close()
        resp.message("✅ Suas contas foram zeradas com sucesso!")
        return str(resp)

    # A IA analisa a mensagem
    dados = extrair_dados_da_mensagem(mensagem_usuario)

    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Ops, o motor travou:\n\n{dados}")
        conn.close()
        return str(resp)

    try:
        intencao = dados.get("intencao", "conversa")
        resposta_da_ia = dados.get("resposta_ia", "")
        
        # CENA 1: É apenas um bate-papo ou dúvida (não salva no banco)
        if intencao == "conversa" or not dados.get("transacao"):
            resp.message(resposta_da_ia)
            
        # CENA 2: É uma transação financeira (salva no banco e mostra extrato)
        else:
            transacao = dados["transacao"]
            categoria = str(transacao.get('categoria', 'Geral')).capitalize()
            valor_str = str(transacao.get('valor', 0)).replace(",", ".")
            valor_absoluto = abs(float(valor_str))
            tipo = str(transacao.get('tipo', 'gasto')).lower()
            
            # Ganho negativo para matemática fechar
            if tipo == 'ganho' or tipo == 'receita':
                valor_banco = -valor_absoluto
            else:
                valor_banco = valor_absoluto
                
            data_atual = datetime.now().strftime("%Y-%m-%d")
            cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', (data_atual, categoria, valor_banco))
            conn.commit()
            
            # Monta o extrato
            mes_atual = datetime.now().strftime("%Y-%m")
            cursor.execute('SELECT categoria, valor FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
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
                    extrato_txt += f"+ {cat_formatada}: R$ {val_formatado}\n"
                else:
                    extrato_txt += f"- {cat_formatada}: R$ {val_formatado}\n"
            
            total_formatado = f"{total:.2f}".replace(".", ",")
            extrato_txt += f"\ntotal do mês = {total_formatado}"
            
            # Junta a resposta humana da IA com o extrato bonitinho
            mensagem_final = f"🤖 {resposta_da_ia}\n\n{extrato_txt}"
            resp.message(mensagem_final)
            
    except Exception as e:
        resp.message(f"Erro interno ao processar os dados: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)