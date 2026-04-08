const ALLOWED = new Set(["start", "stop", "status"]);

module.exports = async function handler(req, res) {
  const base = process.env.TRADER_API_BASE_URL;
  if (!base) {
    return res.status(500).json({ error: "missing_TRADER_API_BASE_URL" });
  }

  const action = String(req.query.action || "status").toLowerCase();
  if (!ALLOWED.has(action)) {
    return res.status(400).json({ error: "invalid_action", allowed: [...ALLOWED] });
  }

  const target = `${base}/control/${action}`;
  const method = action === "status" ? "GET" : "POST";
  try {
    const r = await fetch(target, {
      method,
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
