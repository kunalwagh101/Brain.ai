import type { NextRequest } from "next/server";

export function browserOrigin(request: Pick<NextRequest, "headers" | "nextUrl">): string {
  const host = request.headers.get("host") ?? request.nextUrl.host;
  const protocol = process.env.NODE_ENV === "production" ? "https:" : request.nextUrl.protocol;
  if (!/^[a-z0-9.\-:[\]]+$/i.test(host)) throw new Error("Invalid request Host");
  return new URL(`${protocol}//${host}`).origin;
}
