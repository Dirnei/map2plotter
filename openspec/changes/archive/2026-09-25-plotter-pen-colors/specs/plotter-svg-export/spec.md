# Spec Delta

## MODIFIED Requirements

### Requirement: One layer per pen colour
Paths SHALL be grouped into SVG layers (`<g>` with `inkscape:groupmode="layer"`), one per distinct theme colour used. Theme keys that share a colour value SHALL share one layer. Each layer SHALL set its `stroke` to that colour and SHALL have an `inkscape:label` that includes the colour and the element types it contains.

Inside a layer, the paths of each element type (`water`, `parks`, each road class and `text`) SHALL be wrapped in their own group. That group SHALL carry the element type as `inkscape:label` and as a `data-key` attribute, and SHALL NOT set its own stroke, so the layer's stroke applies. Every path SHALL be inside exactly one element group. Paths SHALL still be ordered to reduce pen-up travel, now within each element group.

#### Scenario: Layers per colour
- **WHEN** a theme uses five distinct road colours plus distinct water, parks and text colours
- **THEN** the SVG contains one layer for each of those distinct colours

#### Scenario: Shared colours merged
- **WHEN** `road_tertiary` and `road_default` have the same colour
- **THEN** their paths are placed in the same layer

#### Scenario: Element groups inside a shared layer
- **WHEN** `road_tertiary` and `road_default` share a colour
- **THEN** that layer contains two groups, with `data-key="road_tertiary"` and `data-key="road_default"`, each holding only the paths of its road class
