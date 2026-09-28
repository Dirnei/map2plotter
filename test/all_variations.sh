#!/bin/bash

# This script generates variations of map posters for Bengaluru, India
# based on the options and guides described in the README.md

# Ensure we are in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "===================================================="
echo "Generating All Variations for Bengaluru, India"
echo "===================================================="

# 1. Basic usage
echo "--- Basic usage ---"
uv run map2plotter -c "Bengaluru" -C "India"

# 2. Themes (from Distance Guide & Themes section)
echo "--- Theme Variations ---"
themes=(
    "gradient_roads" 
    "contrast_zones" 
    "noir" 
    "midnight_blue" 
    "blueprint" 
    "neon_cyberpunk" 
    "warm_beige" 
    "pastel_dream" 
    "japanese_ink" 
    "emerald" 
    "forest" 
    "ocean" 
    "terracotta" 
    "sunset" 
    "autumn" 
    "copper_patina" 
    "monochrome_blue"
)

for theme in "${themes[@]}"; do
    echo "Theme: $theme"
    uv run map2plotter -c "Bengaluru" -C "India" -t "$theme"
done

# 3. Optional Flags (from Optional Flags table)
echo "--- Optional Flags & Overrides ---"
echo "Overriding display name and country label"
uv run map2plotter -c "Bengaluru" -C "India" --display-city "The Garden City" --country-label "Karnataka, India"

echo "Overriding latitude and longitude (central Bengaluru)"
uv run map2plotter -c "Bengaluru" -C "India" -lat 12.9716 -long 77.5946

# 4. Non-Latin display names (the pen font skips characters it cannot draw, with a warning)
echo "--- Non-Latin display names ---"
echo "Kannada display name (skipped glyphs are reported)"
uv run map2plotter -c "Bengaluru" -C "India" -dc "ಬೆಂಗಳೂರು" -dC "India"

# 5. Paper sizes
echo "--- Paper sizes ---"
echo "Square (200x200 mm)"
uv run map2plotter -c "Bengaluru" -C "India" --width 200 --height 200

echo "Landscape (420x297 mm)"
uv run map2plotter -c "Bengaluru" -C "India" --width 420 --height 297

echo "A4 (210x297 mm)"
uv run map2plotter -c "Bengaluru" -C "India" --width 210 --height 297

echo "A3 (297x420 mm)"
uv run map2plotter -c "Bengaluru" -C "India" --width 297 --height 420

# 6. Distance Guide Variations
echo "--- Distance Guide Variations ---"
echo "Small/Dense focal (5000m)"
uv run map2plotter -c "Bengaluru" -C "India" -d 5000

echo "Medium/Focused downtown (10000m)"
uv run map2plotter -c "Bengaluru" -C "India" -d 10000

echo "Large metro view (default 18000m)"
uv run map2plotter -c "Bengaluru" -C "India" -d 18000

# 7. Pens and fills
echo "--- Pens and fills ---"
echo "0.5mm pen with sparse hatching"
uv run map2plotter -c "Bengaluru" -C "India" -d 5000 --pen-width 0.5 --hatch-spacing 1.5

echo "Concentric, outlined water and sparse parks"
uv run map2plotter -c "Bengaluru" -C "India" -d 5000 --water-fill concentric --water-outline --parks-spacing 2

echo "Pen colour override"
uv run map2plotter -c "Bengaluru" -C "India" -d 5000 --color water=#1f5fa8

# 8. Utility flags
echo "--- Utility Flags ---"
echo "Listing themes"
uv run map2plotter --list-themes

echo "Generating for ALL themes at once"
# We'll use a smaller distance to make it faster for testing
uv run map2plotter -c "Bengaluru" -C "India" --all-themes -d 10000

echo "===================================================="
echo "Done! Posters saved to posters/ directory."
echo "===================================================="
