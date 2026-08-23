from flask import Flask, jsonify, request
from flask_cors import CORS

# Importa a função de IA sem alterar o arquivo original do WhatsApp
try:
    from kaliba import extrair_dados_da_mensagem
except ImportError:
    extrair_dados_da_mensagem = None

app = Flask(__name__)
CORS(app)  # Libera o acesso para o Next.js

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    dados_financeiros = {
        "usuario": "Hector",
        "saldo_total": 12500.50,
        "receitas": 15000.00,
        "despesas": 2499.50
    }
    return jsonify(dados_financeiros), 200

@app.route("/api/chat", methods=["POST"])
def api_chat():
    dados = request.get_json() or {}
    mensagem_usuario = dados.get("message", "")

    if not mensagem_usuario:
        return jsonify({"error": "Mensagem vazia"}), 400

    if extrair_dados_da_mensagem:
        try:
            resultado = extrair_dados_da_mensagem(mensagem_usuario, [])
            if isinstance(resultado, dict):
                resposta_texto = resultado.get("resposta_ia", "Não entendi, pode repetir?")
            else:
                resposta_texto = str(resultado)
        except Exception:
            resposta_texto = "Erro ao processar mensagem na IA."
    else:
        resposta_texto = f"Recebido: {mensagem_usuario} (Modo de teste)"

    return jsonify({"reply": resposta_texto}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)