-- depends: 002_add_massing_option

ALTER TABLE polygon
    ADD COLUMN buildable_base jsonb,
    ADD COLUMN geometry_status text,
    ADD COLUMN geometry_reason text;
