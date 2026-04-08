module.exports = async function handler(req, res) {
  const base = process.env.TRADER_API_BASE_URL;
  if (!base) {
    return res.status(500).json({ error: "missing_TRADER_API_BASE_URL" });
  }
  try {
    const r = await fetch(`${base}/health`, {
      headers: {
        Authorization: `Bearer ${process.env.TRADER_API_TOKEN || ""}`,
      },
    });
    const body = await r.json();
    return res.status(r.status).json(body);
  } catch (err) {
    return res.status(502).json({ error: "upstream_unreachable", detail: String(err) });
  }
};
