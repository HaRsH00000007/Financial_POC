import { Fragment, type ReactNode } from "react";

/** Minimal, safe markdown for AI text: paragraphs, "- " lists, **bold**, *italic*, `code`. No HTML. */
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i}>{p.slice(1, -1)}</code>;
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2) return <em key={i}>{p.slice(1, -1)}</em>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

export function Markdown({ text }: { text: string }) {
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <div className="md">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        if (lines.every((l) => /^\s*[-*] /.test(l))) {
          return (
            <ul key={i}>
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>
              ))}
            </ul>
          );
        }
        const listStart = lines.findIndex((l) => /^\s*[-*] /.test(l));
        if (listStart > 0 && lines.slice(listStart).every((l) => /^\s*[-*] /.test(l))) {
          return (
            <Fragment key={i}>
              <p>{inline(lines.slice(0, listStart).join(" "))}</p>
              <ul>
                {lines.slice(listStart).map((l, j) => (
                  <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>
                ))}
              </ul>
            </Fragment>
          );
        }
        return <p key={i}>{inline(lines.join(" "))}</p>;
      })}
    </div>
  );
}
