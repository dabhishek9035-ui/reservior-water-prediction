from __future__ import annotations

from typing import Optional

from .base import ToolContext, ToolResult


async def search_knowledge(ctx: ToolContext, query: str = "", k: int = 3, prefix: Optional[str] = None) -> ToolResult:
    qvec = None
    if ctx.rag.has_embeddings and ctx.settings.use_embeddings:
        try:
            qvec = (await ctx.llm.embed([query]))[0]
        except Exception:
            qvec = None
    hits = ctx.rag.search(query, k=k, qvec=qvec, prefix=prefix)
    if not hits:
        return ToolResult("search_knowledge", "Knowledge base", ["- No matching notes found in the knowledge base."], ok=False)
    lines, srcs = [], []
    for ch, _ in hits:
        text = " ".join(ch.text.split())
        lines.append(f"- [{ch.title}] {text[:650]}")
        srcs.append(ch.source)
    return ToolResult("search_knowledge", "Knowledge base", lines, {"sources": srcs}, detail=", ".join(dict.fromkeys(srcs)))


async def get_region_info(ctx: ToolContext, dam_id: Optional[str] = None, query: str = "") -> ToolResult:
    lines: list[str] = []
    detail = None
    dam = await ctx.registry.get(dam_id)
    if dam:
        lines += [
            f"- {dam['name']} is in {dam.get('district') or 'an unlisted district'}, {dam.get('state') or ''} (location: {dam.get('location') or 'n/a'})",
            f"- Places around the reservoir: {', '.join(dam['nearbyPlaces']) if dam.get('nearbyPlaces') else 'not listed in the registry'}",
            f"- Regions affected if it overflows: {', '.join(dam['affectedRegions']) if dam.get('affectedRegions') else 'not listed in the registry'}",
        ]
    extra = await search_knowledge(ctx, query or (dam["district"] if dam and dam.get("district") else "region"), k=2, prefix="regions/")
    if extra.ok:
        lines += extra.lines
        detail = extra.detail
    return ToolResult("get_region_info", "Dam registry + regional notes", lines or ["- No regional information available."], {"dam_id": dam_id}, ok=bool(lines), detail=detail)
