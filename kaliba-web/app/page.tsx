"use client";

import { useEffect, useState } from "react";
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
  TrendingUp,
  TrendingDown,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface DashboardData {
  usuario: string;
  saldo_total: number;
  receitas: number;
  despesas: number;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Busca os dados da API Python criada no backend
    fetch("https://kaliba-web-api.onrender.com")
      .then((res) => res.json())
      .then((dados) => {
        setData(dados);
        setLoading(false);
      })
      .catch(() => {
        // Fallback caso o backend esteja desligado
        setData({
          usuario: "Hector",
          saldo_total: 12500.5,
          receitas: 15000.0,
          despesas: 2499.5,
        });
        setLoading(false);
      });
  }, []);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(val);

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
            { label: "Dashboard", icon: LayoutDashboard, href: "/", active: true },
            { label: "Chat com IA", icon: MessageSquare, href: "/chat" },
            { label: "Transações", icon: Receipt, href: "/transacoes" },
            { label: "Contas", icon: Wallet, href: "/contas" },
            { label: "Cartões", icon: CreditCard, href: "/cartoes" },
            { label: "Orçamento", icon: PieChart, href: "/orcamento" },
            { label: "Metas", icon: Target, href: "/metas" },
            { label: "Relatórios", icon: BarChart3, href: "/relatorios" },
            { label: "Insights", icon: Sparkles, href: "/insights" },
            { label: "Configurações", icon: Settings, href: "/configuracoes" },
          ].map((item, idx) => (
            <a
              key={idx}
              href={item.href || "#"}
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

        {/* USUÁRIO NO RODAPÉ */}
        <div className="pt-4 border-t border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-medium text-sm">
              H
            </div>
            <div>
              <p className="text-sm font-medium leading-none">{data?.usuario || "Hector"}</p>
              <p className="text-xs text-zinc-500 mt-1">Plano Livre</p>
            </div>
          </div>
          <button className="text-zinc-500 hover:text-zinc-300">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL */}
      <main className="flex-1 overflow-y-auto p-8">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Bom dia, {data?.usuario || "Hector"}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Aqui está um resumo simplificado das suas finanças.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {["Hoje", "Esta semana", "Este mês", "Últimos 3 meses"].map((periodo, idx) => (
              <button
                key={idx}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  idx === 2
                    ? "bg-zinc-800 text-zinc-100 border border-zinc-700"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                }`}
              >
                {periodo}
              </button>
            ))}
          </div>
        </header>

        {/* CARDS PRINCIPAIS */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex items-center justify-between text-zinc-400 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Saldo Total</span>
              <DollarSign className="w-4 h-4" />
            </div>
            <p className="text-2xl font-bold">
              {loading ? "..." : formatCurrency(data?.saldo_total || 0)}
            </p>
            <div className="flex items-center gap-1 text-emerald-400 text-xs mt-2">
              <ArrowUpRight className="w-3.5 h-3.5" />
              <span>+12.4% comparado ao mês passado</span>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex items-center justify-between text-zinc-400 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Receitas</span>
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="text-2xl font-bold text-emerald-400">
              {loading ? "..." : formatCurrency(data?.receitas || 0)}
            </p>
            <p className="text-xs text-zinc-500 mt-2">1 entrada registrada</p>
          </div>

          <div className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex items-center justify-between text-zinc-400 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Despesas</span>
              <TrendingDown className="w-4 h-4 text-rose-400" />
            </div>
            <p className="text-2xl font-bold text-rose-400">
              {loading ? "..." : formatCurrency(data?.despesas || 0)}
            </p>
            <div className="flex items-center gap-1 text-rose-400 text-xs mt-2">
              <ArrowDownRight className="w-3.5 h-3.5" />
              <span>5% acima da meta</span>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex items-center justify-between text-zinc-400 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Economia</span>
              <Sparkles className="w-4 h-4 text-amber-400" />
            </div>
            <p className="text-2xl font-bold">
              {loading ? "..." : formatCurrency((data?.receitas || 0) - (data?.despesas || 0))}
            </p>
            <p className="text-xs text-zinc-500 mt-2">83% da renda mantida</p>
          </div>
        </section>

        {/* INSIGHTS DA IA */}
        <section className="p-5 rounded-xl bg-gradient-to-r from-emerald-950/30 to-zinc-900/50 border border-emerald-500/20 mb-8 flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-emerald-400">Seu assistente percebeu</h3>
            <p className="text-sm text-zinc-300 mt-1">
              Seus gastos com alimentação aumentaram 12% em relação ao mês anterior. Você ainda pode gastar R$ 420,00 até o final do mês sem estourar seu orçamento.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}