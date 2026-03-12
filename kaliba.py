import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = Flask(__name__)

# 1. Configuração da IA (Groq via biblioteca OpenAI)
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("⚠️ A variável GROQ_API_KEY não foi configurada no Render.")

# Inicializa o cliente apontando para os servidores do Groq (O Pulo do Gato!)
client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

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

# 3. Inteligência Artificial no MODO DETETIVE (Groq + Llama 3)
def extrair_dados_da_mensagem(mensagem_usuario):
    prompt_sistema = "Você é um assistente financeiro. Extraia a categoria do gasto e o valor financeiro da mensagem e retorne APENAS um JSON válido."
    prompt_usuario = f"""
    Responda APENAS usando o seguinte esquema JSON: {{"categoria": "Nome", "valor": 00.00}}
    Mensagem: "{mensagem_usuario}"
    """
    
    try:
        # Chamada para o Groq forçando o formato JSON
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ]
        )
        # Extrai o texto da resposta e converte de JSON para dicionário
        conteudo_resposta = response.choices[0].message.content
        return json.loads(conteudo_resposta)
        
    except Exception as e:
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
        resp.message(f"🕵️ Ops, o motor da IA travou. Erro técnico:\n\n{dados}")
        
    elif not isinstance(dados, dict) or 'categoria' not in dados or 'valor' not in dados:
        resp.message("A IA não conseguiu entender. Tente digitar algo como 'comida 18 reais'.")
        
    else:
        # Caminho Feliz (Sucesso!)
        try:
            categoria = str(dados.get('categoria', 'Geral')).capitalize()
            # Garante que o valor venha limpo
            valor_str = str(dados.get('valor', 0)).replace(",", ".")
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
    # Para testes locais. No Render, usaremos o gunicorn.
    app.run(host='0.0.0.0', port=port)