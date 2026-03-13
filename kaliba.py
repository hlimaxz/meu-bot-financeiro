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

# 3. Inteligência Artificial MODO ASSISTENTE PESSOAL EMPÁTICA
def extrair_dados_da_mensagem(mensagem_usuario):
    # Demos uma "alma" para a IA aqui e ensinamos ela a lidar com listas!
    prompt_sistema = """Você é uma assistente financeira pessoal brilhante, empática e muito amigável, exclusiva do seu criador, Kaliba.
    Sua personalidade é calorosa, encorajadora e clara. Você conversa de forma natural, comemora as vitórias financeiras dele e dá dicas valiosas se ele pedir.
    
    Você é capaz de ler mensagens com múltiplos gastos ou ganhos de uma só vez.
    Você DEVE retornar APENAS um objeto JSON válido, com esta estrutura exata:
    {
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta humana, natural, elaborada e empática para o Kaliba.",
        "transacoes": [
            {"categoria": "Nome Curto", "valor": 0.0, "tipo": "gasto" ou "ganho"}
        ]
    }
    
    Regras vitais:
    1. Se ele enviar UMA ou MAIS compras/ganhos (ex: uma lista), extraia TODOS os itens e coloque dentro da lista "transacoes".
    2. Se ele apenas disser "oi" ou pedir conselhos sem passar valores, a intenção é "conversa" e a lista "transacoes" deve ficar vazia [].
    3. A "resposta_ia" deve validar o que ele mandou. Se ele mandar uma lista grande, diga algo como "Uau, bastante coisa! Já registrei tudo aqui para você."
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
        transacoes = dados.get("transacoes", []) # Agora a gente pega a lista inteira!
        
        # CENA 1: É apenas um bate-papo (Lista de transações está vazia)
        if intencao == "conversa" or not transacoes:
            resp.message(f"🤖 {resposta_da_ia}")
            
        # CENA 2: É uma transação (Ou várias de uma vez!)
        else:
            data_atual = datetime.now().strftime("%Y-%m-%d")
            
            # Aqui está a mágica: um "for" que repete a gravação para cada item da lista
            for item in transacoes:
                categoria = str(item.get('categoria', 'Geral')).capitalize()
                valor_str = str(item.get('valor', 0)).replace(",", ".")
                valor_absoluto = abs(float(valor_str))
                tipo = str(item.get('tipo', 'gasto')).lower()
                
                if tipo == 'ganho' or tipo == 'receita':
                    valor_banco = -valor_absoluto
                else:
                    valor_banco = valor_absoluto
                    
                cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', (data_atual, categoria, valor_banco))
            
            # Salva tudo de uma vez
            conn.commit()
            
            # Monta o extrato final
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
                    extrato_txt += f"🟢 + {cat_formatada}: R$ {val_formatado}\n"
                else:
                    extrato_txt += f"🔴 - {cat_formatada}: R$ {val_formatado}\n"
            
            total_formatado = f"{total:.2f}".replace(".", ",")
            
            if total > 0:
                extrato_txt += f"\n📊 Saldo Atual = 🔴 R$ -{total_formatado} (Gastando mais do que ganha)"
            else:
                extrato_txt += f"\n📊 Saldo Atual = 🟢 R$ {str(total_formatado).replace('-', '')} (No azul!)"
            
            # Junta a resposta super humana da IA com o extrato completo
            mensagem_final = f"🤖 {resposta_da_ia}\n\n{extrato_txt}"
            resp.message(mensagem_final)
            
    except Exception as e:
        resp.message(f"Erro interno ao processar os dados: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)