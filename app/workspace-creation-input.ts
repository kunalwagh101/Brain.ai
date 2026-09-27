export function workspaceCreationInput(value: string, suffix: string): { name: string; slug: string } {
  const name = value.trim().replace(/\s+/g, " ");
  if (!name || name.length > 160 || /[\x00-\x1f\x7f]/.test(name) || !/^[a-f0-9]{8}$/.test(suffix)) {
    throw new RangeError("Invalid workspace name or slug suffix");
  }
  const base = name.normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 65)
    .replace(/-$/g, "") || "workspace";
  return { name, slug: `${base}-${suffix}` };
}
