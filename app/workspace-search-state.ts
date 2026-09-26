/** A previous query's excerpt must not remain visible while the next search runs. */
export function resultsForQuery<Item>(
  completed: { query: string; items: Item[] } | null,
  currentQuery: string,
): Item[] | null {
  return completed?.query === currentQuery.trim() ? completed.items : null;
}
