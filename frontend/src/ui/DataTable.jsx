// A table that stays readable on a phone: at desktop width it is a normal
// table; below 720px each row becomes a labelled card (CSS reads data-label).
//
//   <DataTable columns={[{ key, label, render?, align?, primary? }]} rows={rows} rowKey="id" empty={<EmptyState …/>} />
//
// `primary` marks the column shown as the card's heading on a phone.

export default function DataTable({ columns, rows, rowKey = "id", empty, loading = false, caption }) {
  if (loading) {
    return (
      <div className="ui-table-skeleton" aria-busy="true" aria-label="লোড হচ্ছে">
        {[0, 1, 2, 3].map((i) => <span key={i} />)}
      </div>
    );
  }
  if (!rows?.length) return empty ?? null;
  return (
    <div className="ui-table-wrap">
      <table className="ui-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" style={{ textAlign: c.align || "left" }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={typeof rowKey === "function" ? rowKey(row) : row[rowKey]}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  data-label={c.label}
                  className={c.primary ? "is-primary" : undefined}
                  style={{ textAlign: c.align || "left" }}
                >
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
