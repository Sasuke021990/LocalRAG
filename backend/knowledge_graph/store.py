"""
Redis-backed per-pool knowledge graph (task.md §1a).

Nodes are concepts/entities extracted from a user's documents; edges are the
relationships between them. Both are **deduplicated across documents** and
track which document(s) back them (a "source list") so deletion can be exact:
removing a document strips it from every node/edge it contributed to, and any
node/edge whose source list becomes empty is deleted entirely — still-supported
elements are untouched (the "correct" delete semantics locked in task.md §1a).

Key schema (mirrors the webhooks SET+per-item convention)
---------------------------------------------------------
graph_nodes:<user_id>:<pool>            SET    -> {node_id, ...}
graph_node:<user_id>:<pool>:<node_id>   STRING -> JSON {id, label, sources[]}
graph_edges:<user_id>:<pool>            SET    -> {edge_id, ...}
graph_edge:<user_id>:<pool>:<edge_id>   STRING -> JSON {id, source, target, label, sources[]}

``node_id`` is a slug of the concept label, so the same concept mentioned in
two documents collapses to one node. ``edge_id`` is
``<source_id>__<target_id>__<label_slug>``, so the same relationship asserted by
two documents collapses to one edge.

Invariant: every edge's two endpoint nodes always carry a superset of the
edge's own sources (``merge_document`` adds the contributing document to both
endpoints whenever it adds an edge). So while an edge still has any source, its
endpoints still exist — deletion can never strand an edge whose node vanished.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# A single label longer than this is almost certainly the model returning a
# sentence instead of a concept — skip it rather than pollute the graph.
MAX_LABEL_LEN = 80


def _nodes_set_key(user_id: str, pool: str) -> str:
    return f"graph_nodes:{user_id}:{pool}"


def _node_key(user_id: str, pool: str, node_id: str) -> str:
    return f"graph_node:{user_id}:{pool}:{node_id}"


def _edges_set_key(user_id: str, pool: str) -> str:
    return f"graph_edges:{user_id}:{pool}"


def _edge_key(user_id: str, pool: str, edge_id: str) -> str:
    return f"graph_edge:{user_id}:{pool}:{edge_id}"


def _slug(label: str) -> str:
    """Normalize a concept label to a stable id: lowercased, non-alphanumerics
    collapsed to single hyphens. Two spellings that differ only in case or
    punctuation map to the same node."""
    return re.sub(r"[^a-z0-9]+", "-", (label or "").strip().lower()).strip("-")


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip())


def _add_source(sources: List[str], file_name: str) -> List[str]:
    return sources if file_name in sources else [*sources, file_name]


def _load_node(redis_client, user_id: str, pool: str, node_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.get(_node_key(user_id, pool, node_id))
    return json.loads(raw) if raw else None


def _load_edge(redis_client, user_id: str, pool: str, edge_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.get(_edge_key(user_id, pool, edge_id))
    return json.loads(raw) if raw else None


def _upsert_node(redis_client, user_id: str, pool: str, label: str, file_name: str) -> Optional[str]:
    """Create-or-update a node for ``label``, adding ``file_name`` to its
    sources. Returns the node_id, or None if the label was empty/too long."""
    label = _clean_label(label)
    node_id = _slug(label)
    if not node_id or len(label) > MAX_LABEL_LEN:
        return None
    existing = _load_node(redis_client, user_id, pool, node_id)
    if existing:
        existing["sources"] = _add_source(existing.get("sources", []), file_name)
        # Keep the earliest-seen label; only backfill if somehow missing.
        existing.setdefault("label", label)
        node = existing
    else:
        node = {"id": node_id, "label": label, "sources": [file_name]}
    redis_client.set(_node_key(user_id, pool, node_id), json.dumps(node))
    redis_client.sadd(_nodes_set_key(user_id, pool), node_id)
    return node_id


def merge_document(
    redis_client,
    user_id: str,
    pool: str,
    file_name: str,
    nodes: List[str],
    edges: List[Tuple[str, str, str]],
) -> None:
    """
    Merge one document's extracted concepts/relationships into the pool graph.

    ``nodes`` is a list of concept labels; ``edges`` is a list of
    ``(source_label, target_label, relationship_label)`` triples. Each element
    is tagged with ``file_name`` as a source. Endpoint nodes of every edge are
    also upserted with this document as a source, preserving the deletion
    invariant described in the module docstring.
    """
    for label in nodes:
        _upsert_node(redis_client, user_id, pool, label, file_name)

    for src_label, dst_label, rel_label in edges:
        src_id = _upsert_node(redis_client, user_id, pool, src_label, file_name)
        dst_id = _upsert_node(redis_client, user_id, pool, dst_label, file_name)
        if not src_id or not dst_id or src_id == dst_id:
            continue
        rel = _clean_label(rel_label) or "related to"
        edge_id = f"{src_id}__{dst_id}__{_slug(rel)}"
        existing = _load_edge(redis_client, user_id, pool, edge_id)
        if existing:
            existing["sources"] = _add_source(existing.get("sources", []), file_name)
            edge = existing
        else:
            edge = {"id": edge_id, "source": src_id, "target": dst_id, "label": rel, "sources": [file_name]}
        redis_client.set(_edge_key(user_id, pool, edge_id), json.dumps(edge))
        redis_client.sadd(_edges_set_key(user_id, pool), edge_id)

    logger.info(
        f"Graph merged for '{file_name}' (user {user_id}, pool {pool}): "
        f"+{len(nodes)} node label(s), {len(edges)} edge(s)"
    )


def remove_document(redis_client, user_id: str, pool: str, file_name: str) -> None:
    """
    Strip ``file_name`` from every node/edge it contributed to; delete any
    node/edge left with no sources. Safe to call for a document that never
    produced graph data (no-op).
    """
    for edge_id in list(redis_client.smembers(_edges_set_key(user_id, pool))):
        edge = _load_edge(redis_client, user_id, pool, edge_id)
        if not edge:
            redis_client.srem(_edges_set_key(user_id, pool), edge_id)
            continue
        if file_name not in edge.get("sources", []):
            continue
        remaining = [s for s in edge["sources"] if s != file_name]
        if remaining:
            edge["sources"] = remaining
            redis_client.set(_edge_key(user_id, pool, edge_id), json.dumps(edge))
        else:
            redis_client.delete(_edge_key(user_id, pool, edge_id))
            redis_client.srem(_edges_set_key(user_id, pool), edge_id)

    for node_id in list(redis_client.smembers(_nodes_set_key(user_id, pool))):
        node = _load_node(redis_client, user_id, pool, node_id)
        if not node:
            redis_client.srem(_nodes_set_key(user_id, pool), node_id)
            continue
        if file_name not in node.get("sources", []):
            continue
        remaining = [s for s in node["sources"] if s != file_name]
        if remaining:
            node["sources"] = remaining
            redis_client.set(_node_key(user_id, pool, node_id), json.dumps(node))
        else:
            redis_client.delete(_node_key(user_id, pool, node_id))
            redis_client.srem(_nodes_set_key(user_id, pool), node_id)

    logger.info(f"Graph cleaned for removed '{file_name}' (user {user_id}, pool {pool})")


def _pools_with_graph_data(redis_client, user_id: str) -> List[str]:
    """
    Every pool this user has graph data stored under, read back off the key
    space. Derived by stripping the known prefix rather than splitting on
    ":" — a pool name may itself contain a colon (``_sanitize_pool_name``
    only strips path-traversal characters), which would break a naive split.
    """
    prefix = f"graph_nodes:{user_id}:"
    return [key[len(prefix):] for key in redis_client.keys(f"{prefix}*")]


def get_user_graph(redis_client, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    One merged graph across **all** of the user's pools, shaped exactly like
    ``get_pool_graph``'s output so clients can use either interchangeably.

    Pools are an organizational device for retrieval scoping; concepts aren't
    pool-specific, and a per-pool graph made a document uploaded to pool A
    invisible when viewing pool B — surprising, since users think of the
    graph as "everything I know". Node ids are label slugs, so the same
    concept appearing in two pools collapses into one node here (its
    ``source_count`` is the union of backing documents, not a sum, so a
    document filed in both pools isn't double-counted).
    """
    merged_nodes: Dict[str, Dict[str, Any]] = {}
    merged_edges: Dict[str, Dict[str, Any]] = {}
    pools = _pools_with_graph_data(redis_client, user_id)

    for pool in pools:
        for node_id in redis_client.smembers(_nodes_set_key(user_id, pool)):
            node = _load_node(redis_client, user_id, pool, node_id)
            if not node:
                continue
            existing = merged_nodes.get(node["id"])
            if existing:
                existing["sources"].update(node.get("sources", []))
            else:
                merged_nodes[node["id"]] = {
                    "id": node["id"],
                    "label": node.get("label", node["id"]),
                    "sources": set(node.get("sources", [])),
                }

    for pool in pools:
        for edge_id in redis_client.smembers(_edges_set_key(user_id, pool)):
            edge = _load_edge(redis_client, user_id, pool, edge_id)
            if not edge:
                continue
            # Same defensive dangling-edge skip as get_pool_graph.
            if edge["source"] not in merged_nodes or edge["target"] not in merged_nodes:
                continue
            merged_edges.setdefault(edge["id"], {
                "source": edge["source"],
                "target": edge["target"],
                "label": edge.get("label", ""),
            })

    nodes = [
        {"id": n["id"], "label": n["label"], "source_count": len(n["sources"])}
        for n in merged_nodes.values()
    ]
    nodes.sort(key=lambda n: n["label"].lower())
    return {"nodes": nodes, "edges": list(merged_edges.values())}


def get_pool_graph(redis_client, user_id: str, pool: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return ``{"nodes": [...], "edges": [...]}`` for the pool, shaped for the
    D3 client. Each node carries ``id``, ``label``, and ``source_count``; each
    edge carries ``source``, ``target``, ``label``. Dangling edges (an endpoint
    node no longer present) are defensively skipped.
    """
    node_ids = redis_client.smembers(_nodes_set_key(user_id, pool))
    nodes = []
    present = set()
    for node_id in node_ids:
        node = _load_node(redis_client, user_id, pool, node_id)
        if not node:
            continue
        present.add(node_id)
        nodes.append({
            "id": node["id"],
            "label": node.get("label", node["id"]),
            "source_count": len(node.get("sources", [])),
        })

    edges = []
    for edge_id in redis_client.smembers(_edges_set_key(user_id, pool)):
        edge = _load_edge(redis_client, user_id, pool, edge_id)
        if not edge:
            continue
        if edge["source"] not in present or edge["target"] not in present:
            continue
        edges.append({
            "source": edge["source"],
            "target": edge["target"],
            "label": edge.get("label", ""),
        })

    nodes.sort(key=lambda n: n["label"].lower())
    return {"nodes": nodes, "edges": edges}
