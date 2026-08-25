import type { Metadata } from "next";
import "./globals.css";

const siteUrl = new URL("https://brain-control-plane.waghkunal1997.chatgpt.site");
const description = "Company evidence, governed AI access and project progress in one permission-correct workspace.";

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: "Brain",
  description,
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  openGraph: {
    title: "Brain",
    description,
    type: "website",
    url: siteUrl,
    images: [{ url: new URL("/og.png", siteUrl), width: 1200, height: 630, alt: "Brain — Company evidence, with permission" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Brain",
    description,
    images: [new URL("/og.png", siteUrl)],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
