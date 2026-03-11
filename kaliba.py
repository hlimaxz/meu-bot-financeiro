import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import sqlite3

app = Flask(__name__)

# Configuração da IA
genai.configure(api_key="AIzaSyAw_QZcYdHeq53ujB9veraT_fI9c5T3QNg")
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

    # LÓGICA DA IA MELHORADA (PROMPT MAIS RÍGIDO)
    prompt = (
        f"Extraia o item e o valor da frase: '{mensagem_usuario}'. "
        "Responda APENAS no formato: Item | Valor. "
        "Exemplo: Pizza | 50.00. Não escreva frases, apenas os dados separados por '|'."
    )
    
    try:
        response = model.generate_content(prompt)
        # Limpa R$, espaços e troca vírgula por ponto para o Python entender o número
        texto_limpo = response.text.replace("R$", "").replace("reais", "").replace(",", ".").strip()
        
        if "|" in texto_limpo:
            dados = texto_limpo.split('|')
            item = dados[0].strip().capitalize()
            valor = float(dados[1].strip())

            # SALVAR NO BANCO
            cursor.execute("INSERT INTO gastos (item, valor) VALUES (?, ?)", (item, valor))
            conn.commit()
            
            # BUSCAR TOTAL
            cursor.execute("SELECT SUM(valor) FROM gastos")
            total = cursor.fetchone()[0]
            
            resp.message(f"💰 Salvei: {item} - R$ {valor:.2f}\n📉 Total acumulado: R$ {total:.2f}")
        else:
            resp.message("Kaliba, mande assim: 'Comida 18' ou 'Mercado 50.50'")

    except Exception as e:
        print(f"Erro detalhado: {e}") # Isso aparece nos logs do Render
        resp.message("Tive um problema ao processar esse valor. Tente escrever apenas o nome e o número.")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    # Importante: o Render usa portas dinâmicas, o padrão é 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)