import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import sqlite3

app = Flask(__name__)

# Configuração da IA (Substitua pela sua chave)
genai.configure(api_key="SUA_CHAVE_AQUI")
model = genai.GenerativeModel('gemini-pro')

def conectar_banco():
    conn = sqlite3.connect('gastos_kaliba.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            valor REAL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn, cursor

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn, cursor = conectar_banco()

    # COMANDO PARA LIMPAR TUDO
    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos")
        conn.commit()
        conn.close()
        resp.message("✅ Lista de gastos limpa com sucesso! Pode começar do zero.")
        return str(resp)

    # LÓGICA DA IA PARA PROCESSAR GASTO
    prompt = f"Extraia o item e o valor desta frase: '{mensagem_usuario}'. Responda apenas: item, valor. Exemplo: Pizza, 50.00"
    try:
        response = model.generate_content(prompt)
        dados = response.text.split(',')
        item = dados[0].strip()
        valor = float(dados[1].strip())

        # SALVAR NO BANCO
        cursor.execute("INSERT INTO gastos (item, valor) VALUES (?, ?)", (item, valor))
        conn.commit()
        
        # BUSCAR TOTAL
        cursor.execute("SELECT SUM(valor) FROM gastos")
        total = cursor.fetchone()[0]
        
        resp.message(f"💰 Salvei: {item} - R$ {valor:.2f}\n📉 Total acumulado: R$ {total:.2f}")
    except:
        resp.message("Desculpe Kaliba, não entendi o gasto. Tente algo como: 'Padaria 15 reais'")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    # Configuração vital para o Render encontrar a porta correta
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)