import { useState } from "react";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { providerConnectionListSchema } from "../../../lib/dto";

export function ConnectionsPage({ connections, add }: { connections: UseQueryResult<z.infer<typeof providerConnectionListSchema>>; add: UseMutationResult<unknown, Error, { provider: string; label: string; mode: string }> }) {
  const [provider, setProvider] = useState("KRAKEN"); const [label, setLabel] = useState("");
  return <article className="panel wide-panel"><div className="panel-heading"><h2>Conexiones</h2></div>
    <p className="muted">Agrega un proveedor en modo lectura o PAPER. Las claves de trading y los retiros no se habilitan aquí.</p>
    <form className="market-filters" onSubmit={(event) => { event.preventDefault(); add.mutate({ provider, label: label.trim(), mode: "READ_ONLY" }); }}>
      <label>Proveedor<select value={provider} onChange={(event) => setProvider(event.target.value)}>{["BINANCE", "BITSO", "KRAKEN", "COINBASE", "WALLET"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Nombre<input value={label} onChange={(event) => setLabel(event.target.value)} required maxLength={100} /></label>
      <button className="button button-primary" disabled={add.isPending}>Agregar conexión</button>
    </form>
    {add.isError && <p className="error" role="alert">No se pudo agregar la conexión.</p>}
    <div className="markets-table-wrap"><table className="markets-table"><thead><tr><th>Proveedor</th><th>Nombre</th><th>Modo</th><th>Estado</th></tr></thead><tbody>{(connections.data?.rows ?? []).map((row) => <tr key={row.id}><td>{row.provider}</td><td>{row.label}</td><td>{row.mode}</td><td>{row.status}</td></tr>)}</tbody></table></div>
    {!connections.isPending && (connections.data?.rows.length ?? 0) === 0 && <p className="muted">Aún no hay conexiones.</p>}
  </article>;
}
