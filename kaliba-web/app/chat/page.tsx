"use client";

import { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Receipt,
  Wallet,
  CreditCard,
  PieChart,
  Target,
  BarChart3,
  Sparkles,
  Settings,
  LogOut,
  Send,
  Bot,
  User,
  Paperclip,
  X,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Olá, Hector! Sou a Kaliba, sua assistente financeira. Como posso ajudar suas finanças hoje?",
    },
  ]);
  const [input, setInput] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setImage(null);
  };

  const handleSend = async (textToSend?: string) => {
    const query = textToSend || input;
    if ((!query.trim() && !image) || loading) return;

    const userMsgContent = query || "[Comprovante/Imagem enviada]";
    const userMsg: Message = { role: "user", content: userMsgContent };

    setMessages((prev) => [...prev, userMsg]);
    
    const payload = {
      message: query,
      image: image,
    };

    if (!textToSend) setInput("");
    setImage(null);
    setLoading(true);

    try {
      const res = await fetch("https://kaliba-web-api.onrender.com/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply || "Resposta recebida." },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Desculpe, não consegui conectar ao servidor no momento.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 font-sans antialiased">
      {/* SIDEBAR */}
      <aside className="w-64 border-r border-zinc-800 p-5 flex flex-col justify-between hidden md:flex">
        <div>
          <div className="flex items-center gap-3 px-2 mb-8">
            <div className="h-8 w-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
              K
            </div>
            <span className="font-semibold text-lg tracking-tight">Kaliba</span>
          </div>

          <nav className="space-y-1">
            {[
              { label: "Dashboard", icon: LayoutDashboard, href: "/" },
              { label: "Chat com IA", icon: MessageSquare, active: true, href: "/chat" },
              { label: "Transações", icon: Receipt },
              { label: "Contas", icon: Wallet },
              { label: "Cartões", icon: CreditCard },
              { label: "Orçamento", icon: PieChart },
              { label: "Metas", icon: Target },
              { label: "Relatórios", icon: BarChart3 },
              { label: "Insights", icon: Sparkles },
              { label: "Configurações", icon: Settings },
            ].map((item, idx) => (
              <a
                key={idx}
                href={item.label === "Chat com IA" ? "/chat" : item.label === "Dashboard" ? "/" : "#"}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  item.active
                    ? "bg-zinc-800/80 text-zinc-100 font-medium"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </a>
            ))}
          </nav>
        </div>

        <div className="pt-4 border-t border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-medium text-sm">
              H
            </div>
            <div>
              <p className="text-sm font-medium leading-none">Hector</p>
              <p className="text-xs text-zinc-500 mt-1">Plano Livre</p>
            </div>
          </div>
          <button className="text-zinc-500 hover:text-zinc-300">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* ÁREA DO CHAT */}
      <main className="flex-1 flex flex-col h-screen">
        <header className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">Assistente Kaliba</h1>
              <p className="text-xs text-zinc-400">Online • Visão Multimodal Ativa</p>
            </div>
          </div>
        </header>

        {/* MENSAGENS */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-3 max-w-2xl ${
                msg.role === "user" ? "ml-auto flex-row-reverse" : ""
              }`}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-semibold ${
                  msg.role === "user"
                    ? "bg-zinc-800 border border-zinc-700 text-zinc-200"
                    : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                }`}
              >
                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div
                className={`p-4 rounded-2xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-emerald-600 text-zinc-50 rounded-tr-none"
                    : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-none"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-start gap-3 max-w-2xl">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800 text-zinc-400 text-sm animate-pulse">
                Analisando imagem e finanças...
              </div>
            </div>
          )}
        </div>

        {/* SUGESTÕES INICIAIS */}
        {messages.length <= 2 && (
          <div className="px-6 pb-3 flex flex-wrap gap-2">
            {[
              "Quanto gastei este mês?",
              "Onde estou gastando mais?",
              "Como posso economizar?",
              "Quanto posso gastar hoje?",
            ].map((suggest, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(suggest)}
                className="text-xs px-3 py-1.5 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                {suggest}
              </button>
            ))}
          </div>
        )}

        {/* INPUT E BOTÃO DE ANEXO */}
        <div className="p-4 border-t border-zinc-800">
          {image && (
            <div className="mb-2 inline-flex items-center gap-2 bg-zinc-800 p-1.5 px-3 rounded-lg border border-zinc-700 text-xs">
              <img src={image} alt="Preview" className="w-6 h-6 object-cover rounded" />
              <span className="text-zinc-300">Imagem selecionada</span>
              <button onClick={removeImage} className="text-zinc-400 hover:text-zinc-100 ml-1">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl p-2 focus-within:border-zinc-700"
          >
            {/* Botão de Anexo */}
            <label
              htmlFor="upload-input"
              className="p-2 text-zinc-400 hover:text-zinc-200 cursor-pointer rounded-lg hover:bg-zinc-800 transition-colors"
              title="Anexar comprovante ou imagem"
            >
              <Paperclip className="w-4 h-4" />
            </label>
            <input
              id="upload-input"
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleImageUpload}
            />

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Envie uma mensagem ou foto de comprovante..."
              className="flex-1 bg-transparent px-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none"
            />

            <button
              type="submit"
              disabled={loading || (!input.trim() && !image)}
              className="p-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}