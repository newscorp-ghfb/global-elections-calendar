// Which links a feed may open (P142, spec 12.6). Pure: a link is only ever opened through
// safeLink, which gives back the parsed URL, the source's home page, or null.

export const SOURCES = [
  { key: "electionguide", name: "ElectionGuide", hosts: ["electionguide.org"], home: "https://www.electionguide.org/" },
  { key: "osce", name: "OSCE/ODIHR", hosts: ["odihr.osce.org", "osce.org"], home: "https://odihr.osce.org/" },
  { key: "wikipedia", name: "Wikipedia", hosts: ["en.wikipedia.org"], home: "https://en.wikipedia.org/" },
  { key: "ndi", name: "NDI", hosts: ["ndi.org"], home: "https://www.ndi.org/" },
  { key: "aweb", name: "A-WEB", hosts: ["aweb.org"], home: "https://www.aweb.org/" },
  { key: "eisa", name: "EISA", hosts: ["eisa.org"], home: "https://www.eisa.org/" },
  { key: "ipu", name: "IPU", hosts: ["data.ipu.org"], home: "https://data.ipu.org/" },
  { key: "carter", name: "Carter Center", hosts: ["cartercenter.org"], home: "https://www.cartercenter.org/" },
  { key: "eeas", name: "EEAS", hosts: ["eeas.europa.eu"], home: "https://www.eeas.europa.eu/" },
];

// The source with this key or display name (cards use names, attention items use keys), else null.
export function sourceOf(nameOrKey) {
  if (typeof nameOrKey !== "string") return null;
  return SOURCES.find((s) => s.key === nameOrKey || s.name === nameOrKey) ?? null;
}

// The display name of a known source, else the argument itself.
export function sourceName(nameOrKey) {
  const source = sourceOf(nameOrKey);
  return source === null ? nameOrKey : source.name;
}

function allowed(source, hostname) {
  return source.hosts.some((h) => hostname === h || hostname.endsWith("." + h));
}

// The URL to open: the parsed link when it is https, has no user info, port 443 and an allowed
// host; the source's home page for any other link; null for a source we do not know.
export function safeLink(nameOrKey, url) {
  const source = sourceOf(nameOrKey);
  if (source === null) return null;
  if (typeof url !== "string") return source.home;
  try {
    const parsed = new URL(url);
    if (
      parsed.protocol === "https:" &&
      parsed.username === "" &&
      parsed.password === "" &&
      parsed.port === "" &&
      allowed(source, parsed.hostname)
    ) {
      return parsed.href;
    }
  } catch {
    // not an absolute URL: the home page
  }
  return source.home;
}
