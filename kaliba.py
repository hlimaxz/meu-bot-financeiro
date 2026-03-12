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

# Inicializa o cliente apontando para os servidores do Groq
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

# 3. Inteligência Artificial no MODO DETETIVE (Agora entende Ganhos)
def extrair_dados_da_mensagem(mensagem_usuario):
    prompt_sistema = "Você é um assistente financeiro. Extraia a categoria da transação, o valor, e classifique se é um 'gasto' ou 'ganho'. Retorne APENAS um JSON válido."
    prompt_usuario = f"""
    Responda APENAS usando o seguinte esquema JSON: {{"categoria": "Nome", "valor": 00.00, "tipo": "gasto" ou "ganho"}}
    Regra: Se a pessoa comprou/pagou, o tipo é "gasto". Se a pessoa recebeu/ganhou dinheiro, o tipo é "ganho".
    Mensagem: "{mensagem_usuario}"
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ]
        )
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
        resp.message("✅ Lista de movimentações limpa com sucesso!")
        return str(resp)

    # Processa com IA
    dados = extrair_dados_da_mensagem(mensagem_usuario)

    # --- O BOT "DEDO DURO" ---
    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Ops, o motor da IA travou. Erro técnico:\n\n{dados}")
        
    elif not isinstance(dados, dict) or 'categoria' not in dados or 'valor' not in dados:
        resp.message("A IA não conseguiu entender. Tente digitar algo como 'comida 18 reais' ou 'ganhei 50 do pai'.")
        
    else:
        # Caminho Feliz (Sucesso!)
        try:
            categoria = str(dados.get('categoria', 'Geral')).capitalize()
            # Garante que o valor venha limpo
            valor_str = str(dados.get('valor', 0)).replace(",", ".")
            valor_absoluto = abs(float(valor_str))
            tipo = str(dados.get('tipo', 'gasto')).lower()
            
            # A MÁGICA: Ganho vira negativo para subtrair do total de gastos
            if tipo == 'ganho' or tipo == 'receita':
                valor_banco = -valor_absoluto
            else:
                valor_banco = valor_absoluto
                
            data_atual = datetime.now().strftime("%Y-%m-%d")

            # Salva no banco
            cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', 
                           (data_atual, categoria, valor_banco))
            conn.commit()
            
            # --- MONTAGEM DA LISTA ESTILO EXTRATO ---
            mes_atual = datetime.now().strftime("%Y-%m")
            cursor.execute('SELECT categoria, valor FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
            registros = cursor.fetchall()
            
            # Dicionário para deixar o mês em Português
            meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
            nome_mes = meses_pt[datetime.now().strftime("%m")]
            
            resposta_txt = f"🗓️ Agenda Mês: {nome_mes}\n✅ Movimentações:\n"
            
            total = 0.0
            for cat, val in registros:
                total += val
                cat_formatada = cat.lower()
                val_formatado = f"{abs(val):.2f}".replace(".", ",")
                
                if val < 0: # É um ganho
                    resposta_txt += f"+ {cat_formatada}: R$ {val_formatado}\n"
                else:       # É um gasto
                    resposta_txt += f"- {cat_formatada}: R$ {val_formatado}\n"
            
            total_formatado = f"{total:.2f}".replace(".", ",")
            resposta_txt += f"\ntotal do mês = {total_formatado}"
            
            resp.message(resposta_txt)
            
        except Exception as e:
            resp.message(f"Erro ao salvar no banco: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)