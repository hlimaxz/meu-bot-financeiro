import sqlite3
import json
import google.generativeai as genai
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# ==========================================
# 1. CONFIGURAÇÕES INICIAIS
# ==========================================
# Cole sua nova chave do Gemini aqui
CHAVE_API_GEMINI = "AIzaSyAw_QZcYdHeq53ujB9veraT_fI9c5T3QNg"
genai.configure(api_key=CHAVE_API_GEMINI)
model = genai.GenerativeModel('gemini-2.5-flash')

app = Flask(__name__)

# ==========================================
# 2. BANCO DE DADOS
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
    conn.commit()
    return conn

# ==========================================
# 3. INTELIGÊNCIA ARTIFICIAL
# ==========================================
def extrair_dados_da_mensagem(mensagem_usuario):
    prompt = f"""
    Você é um assistente financeiro. Leia a mensagem do usuário e extraia a categoria do gasto e o valor.
    Responda EXATAMENTE neste formato JSON, sem nenhum texto extra ou formatação markdown:
    {{"categoria": "Nome da Categoria", "valor": 00.00}}
    Mensagem: "{mensagem_usuario}"
    """
    resposta = model.generate_content(prompt)
    try:
        texto_limpo = resposta.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpo)
    except:
        return None

# ==========================================
# 4. LÓGICA DO BOT
# ==========================================
def gerar_relatorio_parcial(conn):
    cursor = conn.cursor()
    mes_atual = datetime.now().strftime("%Y-%m")
    cursor.execute('SELECT categoria, valor FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
    gastos = cursor.fetchall()
    
    total = sum(gasto[1] for gasto in gastos)
    
    resposta = "Agenda de gastos do mês:\n"
    for gasto in gastos:
        resposta += f"{gasto[0]} - R$ {gasto[1]:.2f}\n"
    resposta += f"\n*Total parcial: R$ {total:.2f}*"
    return resposta

# ==========================================
# 5. CONEXÃO COM O WHATSAPP (TWILIO + FLASK)
# ==========================================
@app.route('/whatsapp', methods=['POST'])
def bot_whatsapp():
    mensagem_recebida = request.values.get('Body', '').lower()
    dados = extrair_dados_da_mensagem(mensagem_recebida)
    
    if not dados:
        resposta_texto = "Desculpe, não consegui entender o valor e a categoria. Pode tentar de novo?"
    else:
        categoria = dados['categoria'].capitalize()
        valor = float(dados['valor'])
        data_atual = datetime.now().strftime("%Y-%m-%d")

        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', 
                       (data_atual, categoria, valor))
        conn.commit()
        resposta_texto = gerar_relatorio_parcial(conn)

    resp = MessagingResponse()
    resp.message(resposta_texto)
    return str(resp)

if __name__ == "__main__":
    conectar_banco()
    print("Servidor rodando! Aguardando mensagens do WhatsApp...")
    app.run(port=5000)