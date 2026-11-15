// The D1 binding of the S24 collector tests: Node's built-in SQLite behind the D1 calls the collector uses
// (prepare, bind, first, run, all, batch), as the D1 Worker API docs describe them. A batch is one transaction.
// The schema is the collector's own schema.sql.
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

const SCHEMA = new URL("../../src/collector/schema.sql", import.meta.url);

export function fakeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(SCHEMA, "utf8"));
  const statement = (sql: string, values: unknown[] = []): any => ({
    bind: (...v: unknown[]) => statement(sql, v),
    first: async (column?: string) => {
      const row = db.prepare(sql).get(...(values as never[])) as Record<string, unknown> | undefined;
      return row === undefined ? null : column ? row[column] : { ...row };
    },
    all: async () => ({ success: true, meta: {}, results: db.prepare(sql).all(...(values as never[])).map((r) => ({ ...r })) }),
    run: async () => {
      const info = db.prepare(sql).run(...(values as never[]));
      return { success: true, meta: { changes: Number(info.changes) }, results: [] };
    },
  });
  return {
    prepare: (sql: string) => statement(sql),
    batch: async (statements: any[]) => {
      db.exec("BEGIN");
      try {
        const results = [];
        for (const s of statements) results.push(await s.run());
        db.exec("COMMIT");
        return results;
      } catch (e) {
        db.exec("ROLLBACK");
        throw e;
      }
    },
    rows: (sql: string) => db.prepare(sql).all().map((r) => ({ ...r })) as Record<string, unknown>[],
  };
}
