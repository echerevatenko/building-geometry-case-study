# Design note

## Problem interpretation

I see this task as a decision-support tool for early-stage building massing.

The goal is to help a user quickly understand what can be built on a given site under a set of constraints, and how close the result gets to the target GFA. It is not meant to design the final building, but to make early trade-offs visible: footprint vs. height, stricter setbacks vs. less area, one option vs. another.

I read the task as three connected responsibilities:

- validate the user-provided site coordinates and derive a usable buildable base where possible;
- generate a deterministic massing from constraints such as setback, coverage, height, floor count, floor-to-floor height, corridor width, and target GFA;
- support exploration by saving options, branching from previous decisions, and visualizing the result.

The prototype focuses on geometry validation, deterministic massing generation, saved options, branching, basic tree management, and 3D visualization. It is not a full zoning engine, a detailed architectural design tool, or an optimizer.

## Domain model

The domain model is built around two main concepts: the site geometry and the massing option.

A Polygon represents the site provided by the user. It is defined by site_polygon, a list of planar coordinates in metres. From this polygon, the system derives a buildable_base: the geometry that can actually be used for massing after validation and setback logic are applied. If the input geometry produces multiple valid buildable areas, the prototype chooses the largest one as the buildable base.

Each polygon also has a geometry_status and an optional geometry_reason. The status describes whether the geometry is suitable for massing. If it is not suitable, the reason explains why, for example because the polygon is degenerate, self-intersecting, collapsed after setback, or does not contain any usable buildable area.

A MassingOption represents one possible development scenario for the site. It stores the constraints used to generate the option:

`setback_m`

`floor_to_floor_m`

`max_height_m`

`max_floors`

`site_coverage_ratio`

`target_gfa`

For each option, the backend computes:

`floor_count`

`footprint_area`

`gfa`

verification_result

The verification_result describes whether a valid building massing can be produced under the selected constraints, and whether the requested GFA target is reachable.

Saved options form a decision tree. A root option is created from the initial site and constraints. Any existing option can then be branched by changing one or more constraints and recomputing the massing. The new option stores a reference to its parent option, which makes the tree explicit and allows the frontend to navigate the history of design decisions.

## Algorithm

I split the algorithm into two stages: preparing the site geometry and generating the massing.

### Site geometry preparation

The input coordinates are converted into a Shapely geometry. Shapely is used because it provides reliable tools for validating and repairing polygons, calculating areas, and performing geometric operations such as setbacks, including for irregular or problematic shapes.

If the geometry is missing or empty, it is rejected immediately. If it is invalid, the algorithm applies make_valid as a repair step. The repaired result may be a Polygon, MultiPolygon, or GeometryCollection, so the algorithm keeps only polygonal parts with area greater than AREA_EPS (1.0 m²). This removes tiny slivers that can appear after repair.

If several usable polygons remain, the largest one is selected as the base site geometry. This is a simplification: the prototype does not try to infer user intent across multiple disconnected areas. The selected base must also be larger than min_site_area; otherwise the site is rejected as too small for massing.

The geometry status is reported as:

valid — one usable polygon was accepted without repair;
semi_valid — the geometry was repaired, or multiple usable parts were produced and the largest was selected;
invalid — no usable area could be derived, or the area is below the minimum threshold.

### Massing generation

The massing step uses a few explicit assumptions.

The buildable footprint is first derived from the setback-inset geometry. If site_coverage_ratio is provided, it is applied as an additional area cap on top of that geometry. The effective maximum footprint area is the smaller of the setback-derived area and site_area * site_coverage_ratio.

If the selected footprint needs to be smaller than the available setback area, the algorithm performs an actual geometric reduction rather than only changing the reported area. It erodes the footprint inward toward the target area. Because this reduction changes the geometry itself, the final footprint area may end up slightly below the requested target or cap, which can also result in a slightly lower reported GFA.

target_gfa is treated as a target to approach, not as a strict minimum. The algorithm first determines the largest massing allowed by the constraints. If the target GFA is lower than that maximum, it tries to reduce the footprint so the resulting GFA is closer to the target. If the target is higher than the maximum achievable GFA, the option is returned with the maximum possible metrics and marked as unable to satisfy the target.

The algorithm also uses a minimum corridor width setting to avoid producing floor plates that are mathematically valid but too narrow to be meaningful.

The floor count is derived from the available floor and height limits. If both max_height_m and max_floors are provided, the smaller resulting limit is used. If only one is provided, that limit is used. If neither limit is provided, or if the limits allow zero floors, the option is marked as infeasible.

The massing generation step assumes that the input site geometry has already been validated during site parsing and saving. If the geometry is invalid, massing generation cannot proceed and returns an error indicating that the site polygon is not valid.

For each option, the backend reports the final footprint geometry, footprint area, floor count, height, GFA, and a verification result explaining whether the massing can be generated and whether the target GFA can be satisfied under the selected constraints.



## API contract

All routes under `/api/v1`.

**Polygons**

- `GET /polygons` → `[PolygonOut]`
- `POST /polygons` `{title, site_polygon}` → `201` (site polygon **required**; `empty`
  geometry → `422`) - saves the polygon and validates its derived geometry
- `GET /polygons/{id}` → `PolygonOut` | `404`
- `PATCH /polygons/{id}` `{title?, site_polygon?}` → recomputes and revalidates derived geometry when the
  site changes | `404`
- `DELETE /polygons/{id}` → `204` (soft-cascade) | `404`
- `GET /polygons/{id}/massing-options` → `[MassingOptionOut]` (flat, pre-ordered)

**Massing options**

- `POST /massing-options` `{polygon_id, parent_id?, name?, constraints?, floor_count?,
  footprint_area?, gfa?, verification_result?}` → `201` | `404` (unknown polygon) |
  `409` (site has no buildable base). Branching is client-driven: a child arrives
  pre-filled with the parent's state.
- `PATCH /massing-options/{id}` (partial) → `MassingOptionOut` | `404`
- `DELETE /massing-options/{id}` → `204` (soft-deletes the subtree) | `404`
- `POST /massing-options/{id}/generate` `{constraints?}` → `GenerationResult` | `404`.
  A **non-persisting preview**: masses with the body's constraints (falling back to the
  saved ones) against the site's buildable base and returns the result without writing.

**Shapes**

- `PolygonOut`: `…, buildable_base, geometry_status, geometry_reason {name, message}|null`
- `GenerationResult`: `{footprint, floor_count, footprint_area, gfa, verification_result,
  reasons: [{name, message}]}`
- `MassingConstraints`: `{setback_m, floor_to_floor_m, max_height_m, max_floors, site_coverage_ratio, target_gfa}` all optional, all `≥ 0`, `site_coverage_ratio ∈ [0,1]`

## Visualization

The frontend uses three.js to show the site and the generated massing in one interactive scene. I chose this instead of a 2D canvas because building height is an important part of the result, and a simple 3D view makes it easier to understand.

The user sees:

the site boundary as a blue outline;
the buildable area as a green shape on the ground;
the selected massing option as an extruded building volume.

The camera starts in an isometric view and supports orbit and zoom. It is reset only when the site changes. This means the user can rotate or zoom into the model, generate a new option, and keep the same view.

The input geometry is still edited as 2D coordinates. A new polygon is treated as a draft until the user saves it. The user can edit coordinates directly or add points visually, and both inputs stay in sync.

The option workflow is:

create or select from a site;
edit constraints;
generate a preview;
review the metrics and validation messages;
save the option;
branch new options from it.

If WebGL is not available in the browser, the app shows a clear error message instead of an empty canvas.

## Assumptions & trade-offs

The prototype makes a few deliberate simplifications.

First, it assumes one building mass per site. If the setback or geometry repair produces several buildable pieces, the system uses the largest one and reports the site as only partially valid. Supporting several separate buildings on one site is left for future work.

Second, when the footprint needs to be reduced to satisfy site coverage limits or the target GFA, the algorithm shrinks it inward uniformly. This is not the same as an architect optimising the building shape or placement, but it provides a simple and deterministic way to keep the footprint within the allowed area while ensuring that the reported metrics match the generated geometry.

Third, generating a massing does not automatically save it. Generate is used for quick what-if exploration, while Save creates a persistent option in the decision tree. It keeps the workflow explicit: only options the user chooses to save become part of the project history.

Finally, the site is treated as its polygon. Empty geometry is rejected. Degenerate or invalid geometry can be saved with an invalid status, but it cannot be used to generate options until the user fixes it. We intentionally keep such sites in the system so users can review the issue and correct the geometry later. This lets the UI show and explain the problem instead of silently dropping the site.

I also limited the option tree depth to five levels. This is mainly a UI-driven constraint: the option tree is displayed in a relatively small part of the screen, and hierarchy is shown through indentation. Deeper nesting would quickly become hard to read and navigate in the current layout. This is not a domain limitation and could be changed later with a different tree visualization.

I use soft delete for sites and options as a safety measure. The UI shows confirmation prompts, but the option tree is compact and it is still possible for a user to select the wrong site or option by mistake. Soft delete makes accidental deletion recoverable at the data level. This is a prototype-level trade-off. Reads filter out soft-deleted rows, so deleted entities disappear from the normal UI, but the data is still kept in the database. In a production version, this should be completed with a proper retention policy, for example a scheduled cleanup job that permanently deletes soft-deleted rows after a recovery window.

## Edge cases

The prototype handles edge cases in two areas: geometry/massing and saved option data.

Geometry and massing

Concave plots are supported through Shapely’s inset operation. The setback follows the shape of the polygon, including reflex corners.

If the setback removes the entire usable area, the option is marked as infeasible with setback_collapses_footprint. If the setback creates several separate buildable pieces, the prototype uses the largest one and returns setback_split_used_largest_piece.

Invalid or self-intersecting input is repaired when the site is saved, where possible. Such sites are marked as semi_valid if a usable base can be derived. During massing generation, however, invalid base geometry is not repaired again; it is reported as invalid and no massing is generated.

Very small or degenerate sites are marked as invalid and cannot be used to create options. Thin footprint parts are also removed using the minimum corridor width rule. If the remaining footprint is too thin to be useful, the option is marked as infeasible with footprint_too_thin.

Constraint sets can also make a massing impossible. For example, if neither a height limit nor a floor-count limit is provided, or if the height limit is lower than one floor-to-floor height, the option is returned as infeasible with an explicit reason.

If target_gfa cannot be reached under the selected constraints, the algorithm returns the best feasible massing it can produce and marks the target as unmet with gfa_target_unmet.

Saved options and data integrity

Saved options are also guarded against invalid tree states. Deleting an option removes its descendants as a subtree. Deleting a site soft-deletes its related options, and soft-deleted rows are excluded from reads.

The API supports re-rooting an option by setting parent_id to null. It also distinguishes between leaving a field unchanged and explicitly clearing it during partial updates. This design also leaves room for future support of moving options within the tree by updating their parent relationships, although that functionality is not currently exposed in the UI.

The UI also prevents creating options from invalid or unsaved state. A user cannot add options to an invalid site, because there is no usable base geometry for massing. A user also cannot branch from an unsaved option or create options for an unsaved site, because those entities do not yet have stable database identities. This keeps the option tree consistent and avoids branches that point to temporary client-side state.

## What I would do next

I would split the roadmap into near-term improvements and longer-term product/architecture work.

### Next week

First, I would improve the preview workflow. In the current prototype, the 3D scene updates only after the user clicks `Generate` and the backend recomputes the geometry. This keeps the result consistent, but makes exploration feel slower than it should.

I would keep the backend as the source of truth for saved options, final geometry, metrics, and validation reasons. At the same time, the frontend could show a lightweight live preview while the user edits constraints, for example by updating height, floor count, or an approximate massing immediately. The final result would still be confirmed by backend generation.

Second, I would add a small 2D site editor. Right now, the user enters the site either as a JSON coordinate array or point by point. This works for testing, but it is slow and not very intuitive.

A 2D editor would let the user draw a polygon visually, move points, see edge lengths, and then convert the result into the coordinate array used by the main tool. I would treat this as a high-ROI feature: it does not change the backend model, but it would make site creation much easier and reduce input mistakes.

Third, I would add side-by-side option comparison. Comparing alternatives is one of the core workflows of the case study, and the current UI makes the user inspect options one at a time. I would split the screen into two views, each showing a selected option with its geometry and metrics. This would make differences in footprint, height, floor count, GFA, and validation reasons much easier to understand.

Fourth, I would expose tree cleanup in the UI. The backend already supports changing an option’s parent, so I would add a clear move/re-parent action. The computed massing result of a saved option should remain immutable, but its position in the decision tree can change. This lets the user clean up the hierarchy without rewriting the option’s actual design record.

Fifth, I would improve the 3D height visualization. The current view shows each option as one solid extruded mass. I would show the building floor by floor, so the user can better understand how the computed floor count relates to the total height.

### Later roadmap

After that, I would expand the constraint model. The current prototype supports a small set of constraints: setback, site coverage, height, floor count, floor-to-floor height, minimum corridor width, and target GFA. A more realistic massing tool would need different setbacks per boundary edge, minimum distances between buildings, maximum building depth, access points, fire lanes, frontage rules, and different height zones within the same site.

I would also improve the geometry model. The current implementation uses one buildable polygon per site. If repair or setback produces multiple buildable areas, the prototype uses the largest one. A future version should support all usable buildable areas and allow massing across more than one part of the site.

Footprint generation should also become more design-aware. Today, when the full buildable area is larger than needed, the algorithm shrinks the footprint inward in a deterministic way. This keeps the result valid, but it is not the same as choosing the best building placement. Future placement strategies could keep the building closer to one edge, prefer a compact shape, preserve the widest part of the footprint, or split the massing across several buildable areas.

I would also make the height model more realistic. The prototype currently assumes one uniform floor-to-floor value. Real projects may have a taller ground floor, podium levels, roof structures, attic space, foundation height, or technical floors. Supporting these separately would make the massing result closer to how building height is evaluated in practice.

Longer term, I would turn the prototype into a multi-user system. This would require RBAC and project-level permissions, so users only see and edit projects they have access to.

I would also add collaboration workflows: inviting users to edit a project, sharing read-only views, and tracking ownership of sites and options.

I would add an audit log for important actions such as creating, saving, moving, deleting options, and changing access. This would make the project history reliable for team work.

If option trees become large or heavily edited, I would revisit the persistence model. A simple `parent_id` is enough for the prototype, but PostgreSQL `ltree` or a closure table would make subtree reads, moves, deletes, and re-parenting easier to scale.

Once the constraint model is richer, I would explore more intelligent footprint generation. For complex sites, the system could generate candidate building shapes from simple primitives or search for a good balance between several buildings on the same site.

At that point, more advanced optimization techniques could become useful, including evolutionary algorithms or ML-assisted layout exploration. These would only make sense once the system has a clear scoring model for what “better” means: target GFA, compactness, usable floor-plate width, frontage, separation distances, and constraint compliance.

For heavier geometry workflows, I would move long-running computations to background jobs, cache generated results, and store progress separately. But I would expect collaboration, history, and data ownership to become scaling concerns before raw 3D rendering does.
