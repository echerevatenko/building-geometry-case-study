-- depends: 002_add_massing_option

ALTER TABLE polygon
    DROP COLUMN buildable_base,
    DROP COLUMN geometry_status,
    DROP COLUMN geometry_reason;
