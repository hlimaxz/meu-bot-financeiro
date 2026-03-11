import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

app = Flask(__name__)

# 1. Configuração da IA (Voltando para o 2.5-flash que é excelente com JSON)
genai.configure(api_key="AIzaSyAw_QZcYdHeq53ujB9veraT_fI9c5T3QNg")
model = genai.GenerativeModel('gemini-2.5-flash')

# 2. Banco de Dados (Padrão antigo que funcionava bem)
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

# 3. Inteligência Artificial Extraindo JSON
def extrair_dados_da_mensagem(mensagem_usuario):
    prompt = f"""
    Você é um assistente financeiro. Leia a mensagem do usuário e extraia a categoria do gasto e o valor.
    Responda EXATAMENTE neste formato JSON, sem nenhum texto extra ou formatação markdown:
    {{"categoria": "Nome da Categoria", "valor": 00.00}}
    Mensagem: "{mensagem_usuario}"
    """
    try:
        resposta = model.generate_content(prompt)
        texto_limpo = resposta.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpo)
    except:
        return None

# 4. Conexão com WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    # COMANDO PARA LIMPAR TUDO
    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos")
        conn.commit()
        conn.close()
        resp.message("✅ Lista de gastos limpa com sucesso! Pode começar do zero.")
        return str(resp)

    # PROCESSA MENSAGEM COM A IA
    dados = extrair_dados_da_mensagem(mensagem_usuario)

    if not dados:
        resp.message("Desculpe, não consegui entender o valor e a categoria. Pode tentar de novo? Exemplo: 'Comida 18'")
    else:
        try:
            categoria = dados['categoria'].capitalize()
            # Garante que o valor venha como float, mesmo se tiver vírgula na IA
            valor_str = str(dados['valor']).replace(",", ".")
            valor = float(valor_str)
            data_atual = datetime.now().strftime("%Y-%m-%d")

            # Salva no banco
            cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', 
                           (data_atual, categoria, valor))
            conn.commit()
            
            # Pega o total do mês para exibir
            mes_atual = datetime.now().strftime("%Y-%m")
            cursor.execute('SELECT SUM(valor) FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
            resultado = cursor.fetchone()[0]
            total = resultado if resultado else 0.0
            
            resp.message(f"✅ Registrado: {categoria} - R$ {valor:.2f}\n📉 Total do Mês: R$ {total:.2f}")
        except Exception as e:
            print(f"Erro ao salvar: {e}")
            resp.message("Tive um problema ao salvar esse valor no banco.")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    # Mantém a porta dinâmica do Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)