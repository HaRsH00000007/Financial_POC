import { Fragment, type ReactNode } from "react";

function inline(t: string): ReactNode[] {
  return t.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i} className="font-semibold text-ink-950">{p.slice(2, -2)}</strong>;
    if (p.startsWith("_") && p.endsWith("_") && p.length > 2) return <em key={i} className="text-ink-500">{p.slice(1, -1)}</em>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

/** Renders the deterministic markdown report produced by the backend. */
export function ReportView({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[-| ]+\|$/.test(lines[i])) rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      out.push(
        <div key={i} className="my-3 overflow-x-auto rounded-md border border-ink-200">
          <table className="w-full text-[12.5px]">
            <thead className="bg-ink-50 text-left text-ink-600">
              <tr>{rows[0].map((c, j) => <th key={j} className="px-3 py-1.5 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody className="num divide-y divide-ink-100">
              {rows.slice(1).map((r, k) => (
                <tr key={k}>{r.map((c, j) => <td key={j} className="px-3 py-1.5">{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (l.startsWith("# ")) out.push(<h1 key={i} className="text-xl font-semibold text-ink-950">{l.slice(2)}</h1>);
    else if (l.startsWith("## ")) out.push(<h2 key={i} className="mt-6 border-b border-ink-200 pb-1 text-[15px] font-semibold text-ink-950">{l.slice(3)}</h2>);
    else if (l.startsWith("### ")) out.push(<h3 key={i} className="mt-4 text-[13.5px] font-semibold text-ink-900">{l.slice(4)}</h3>);
    else if (l.startsWith("> ")) out.push(<blockquote key={i} className="my-2 border-l-2 border-warn-600 bg-warn-50 px-3 py-1.5 text-[12.5px] text-warn-700">{inline(l.slice(2))}</blockquote>);
    else if (l.startsWith("  - ")) out.push(<div key={i} className="ml-8 text-[12.5px] text-ink-600">– {inline(l.slice(4))}</div>);
    else if (l.startsWith("- ")) out.push(<div key={i} className="ml-2 mt-1 text-[13px] text-ink-800">• {inline(l.slice(2))}</div>);
    else if (l.trim()) out.push(<p key={i} className="my-1.5 text-[13px] text-ink-700">{inline(l)}</p>);
    i++;
  }
  return <article className="max-w-none">{out}</article>;
}
