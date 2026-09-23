import { Link, NavLink, Route, Routes } from "react-router-dom";
import { PactLineProvider, usePactLine } from "./context/PactLineContext";
import { TxBanner, WalletButton } from "./components/Chrome";
import { Board } from "./pages/Board";
import { DealPage } from "./pages/DealPage";
import { NewDeal } from "./pages/NewDeal";
import { Deliver } from "./pages/Deliver";
import { HowItWorks } from "./pages/HowItWorks";
import { EXPLORER_ADDR, formatGen } from "./config";

function Bar() {
  const { stats } = usePactLine();

  return (
    <header className="bar">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" width="20" height="20" fill="none">
            <rect x="4" y="6" width="24" height="20" rx="2.5" stroke="currentColor" strokeWidth="2.4" />
            <path d="M9 13.5h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M9 18.5h8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </span>
        <span className="brand-text">
          <strong>PactLine</strong>
          <em>escrow that opens when the work is real</em>
        </span>
      </Link>

      <nav className="bar-nav" aria-label="Main">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "on" : "")}>
          Deals
        </NavLink>
        <NavLink to="/new" className={({ isActive }) => (isActive ? "on" : "")}>
          Fund a deal
        </NavLink>
        <NavLink to="/how" className={({ isActive }) => (isActive ? "on" : "")}>
          How it works
        </NavLink>
      </nav>

      <div className="bar-meters" aria-label="Live contract state">
        <span className="mini mono">{formatGen(stats.escrow)} GEN in escrow</span>
        <span className="mini mono">{formatGen(stats.payouts)} GEN paid out</span>
      </div>

      <WalletButton />
    </header>
  );
}

function Footer() {
  const { stats, error, wallet } = usePactLine();
  return (
    <footer className="foot">
      <span>
        {stats.deals} deal{stats.deals === 1 ? "" : "s"} · {stats.settledCount} settled ·{" "}
        {stats.appeals} appeal{stats.appeals === 1 ? "" : "s"} ({stats.overturned} overturned)
      </span>
      {wallet.address && (
        <a className="mono" href={EXPLORER_ADDR(wallet.address)} target="_blank" rel="noreferrer">
          {shortMe(wallet.address)}
        </a>
      )}
      {error && <span className="bad">contract unreadable: {error}</span>}
    </footer>
  );
}

function shortMe(a: string): string {
  return a.startsWith("addr#") ? "0x" + a.slice(5, 11) + "…" : a.slice(0, 8) + "…";
}

export default function App() {
  return (
    <PactLineProvider>
      <div className="shell">
        <Bar />
        <TxBanner />
        <main>
          <Routes>
            <Route path="/" element={<Board />} />
            <Route path="/deals/:id" element={<DealPage />} />
            <Route path="/new" element={<NewDeal />} />
            <Route path="/deals/:id/deliver" element={<Deliver />} />
            <Route path="/how" element={<HowItWorks />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </PactLineProvider>
  );
}
