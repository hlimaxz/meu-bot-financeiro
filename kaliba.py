import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

app = Flask(__name__)

# 1. Configuração da IA (Mudei para 1.5-flash para garantir estabilidade)
genai.configure(api_key="AIzaSyAw_QZcYdHeq53ujB9veraT_fI9c5T3QNg")
model = genai.GenerativeModel('gemini-1.5-flash')

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

# 3. Inteligência Artificial no MODO DETETIVE
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
    except Exception as e:
        # A MÁGICA AQUI: Ele vai capturar o erro exato e enviar para o WhatsApp
        return f"ERRO_TECNICO: {str(e)}"

# 4. Conexão com WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    # Comando para limpar
    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos")
        conn.commit()
        conn.close()
        resp.message("✅ Lista de gastos limpa com sucesso!")
        return str(resp)

    # Processa com IA
    dados = extrair_dados_da_mensagem(mensagem_usuario)

    # --- O BOT "DEDO DURO" ---
    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        # Se deu erro, ele mostra exatamente O QUÊ quebrou no Python!
        resp.message(f"🕵️ Ops, o motor da IA travou. Erro técnico:\n\n{dados}")
        
    elif not dados:
        resp.message("A IA não retornou o formato JSON corretamente. Tente de novo.")
        
    else:
        # Caminho Feliz (Sucesso!)
        try:
            categoria = dados['categoria'].capitalize()
            valor_str = str(dados['valor']).replace(",", ".")
            valor = float(valor_str)
            data_atual = datetime.now().strftime("%Y-%m-%d")

            cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', 
                           (data_atual, categoria, valor))
            conn.commit()
            
            mes_atual = datetime.now().strftime("%Y-%m")
            cursor.execute('SELECT SUM(valor) FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
            resultado = cursor.fetchone()[0]
            total = resultado if resultado else 0.0
            
            resp.message(f"✅ Registrado: {categoria} - R$ {valor:.2f}\n📉 Total do Mês: R$ {total:.2f}")
        except Exception as e:
            resp.message(f"Erro ao salvar no banco: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)