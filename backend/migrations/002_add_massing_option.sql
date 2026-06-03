-- depends: 001_add_polygon

CREATE TABLE massing_option (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    polygon_id bigint NOT NULL REFERENCES polygon(id) ON DELETE CASCADE,
    parent_id bigint REFERENCES massing_option(id) ON DELETE CASCADE,
    name text,
    position int NOT NULL DEFAULT 0,
    footprint jsonb,
    constraints jsonb,
    floor_count int,
    footprint_area double precision,
    gfa double precision,
    verification_result text,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CHECK (id <> parent_id)
);

CREATE INDEX idx_massing_option_polygon_parent
ON massing_option (polygon_id, parent_id);

CREATE INDEX idx_massing_option_polygon
ON massing_option (polygon_id);
