-- WS-4: Trust Score View + pgvector kNN helper + provenance helper
-- Depends on: 001_init.sql (entities, facts, source_records tables with pgvector)

-- ---------------------------------------------------------------------------
-- Trust score view
-- Formula: avg(confidence) × source_diversity_factor × recency_decay
-- source_diversity_factor: capped at 1.0 for ≥3 independent sources
-- recency_decay: e^(-days_since_last_fact / 30)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW entity_trust AS
SELECT
    e.id,
    e.canonical_name,
    e.entity_type,
    COALESCE(
        AVG(f.confidence)
        * LEAST(COUNT(DISTINCT f.source_id)::float / 3.0, 1.0)
        * EXP(
            -EXTRACT(EPOCH FROM (NOW() - MAX(f.recorded_at))) / (30.0 * 86400.0)
          ),
        0.0
    ) AS trust_score,
    COUNT(f.id) AS fact_count,
    COUNT(DISTINCT f.source_id) AS source_diversity
FROM entities e
LEFT JOIN facts f ON f.subject_id = e.id AND f.valid_to IS NULL
GROUP BY e.id, e.canonical_name, e.entity_type;


-- ---------------------------------------------------------------------------
-- kNN semantic search over entity embeddings
-- Prefers inference_embedding (Tier B) when present, falls back to name_embedding
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_entities(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 20,
    use_inference_embedding BOOL DEFAULT TRUE
)
RETURNS TABLE(
    id UUID,
    canonical_name TEXT,
    entity_type TEXT,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        CASE
            WHEN use_inference_embedding AND e.inference_embedding IS NOT NULL
                THEN 1.0 - (e.inference_embedding <=> query_embedding)
            ELSE
                1.0 - (e.name_embedding <=> query_embedding)
        END AS similarity
    FROM entities e
    WHERE
        CASE
            WHEN use_inference_embedding AND e.inference_embedding IS NOT NULL
                THEN 1.0 - (e.inference_embedding <=> query_embedding)
            ELSE
                1.0 - (e.name_embedding <=> query_embedding)
        END > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;


-- ---------------------------------------------------------------------------
-- Provenance chain for a single fact
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_fact_provenance_json(p_fact_id UUID)
RETURNS JSON
LANGUAGE sql STABLE
AS $$
    SELECT json_build_object(
        'fact',         row_to_json(f),
        'source_record', row_to_json(sr),
        'superseded_by', (
            SELECT row_to_json(fnew)
            FROM facts fnew
            WHERE fnew.id = f.superseded_by
        )
    )
    FROM facts f
    JOIN source_records sr ON sr.id = f.source_id
    WHERE f.id = p_fact_id;
$$;


-- ---------------------------------------------------------------------------
-- Index: lookup entities by VFS path stored in attrs
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS entities_vfs_path
    ON entities ((attrs->>'vfs_path'));
