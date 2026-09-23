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
uv run python3 create_map_poster.py -c "Bengaluru" -C "India"

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
    uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -t "$theme"
done

# 3. Optional Flags (from Optional Flags table)
echo "--- Optional Flags & Overrides ---"
echo "Overriding display name and country label"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --display-city "The Garden City" --country-label "Karnataka, India"

echo "Overriding latitude and longitude (central Bengaluru)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -lat 12.9716 -long 77.5946

# 4. Multilingual Support (from i18n section)
echo "--- Multilingual Support (i18n) ---"
echo "Kannada (Native script)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -dc "ಬೆಂಗಳೂರು" -dC "ಭಾರत (India)" --font-family "Noto Sans Kannada"

echo "Hindi (Devanagari script)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -dc "बेंगलुरु" -dC "भारत" --font-family "Noto Sans Devanagari"

# 5. Resolution Guide Variations
echo "--- Resolution Guide Variations ---"
echo "Instagram Post (91.4x91.4 mm)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --width 91.4 --height 91.4

echo "Mobile Wallpaper (91.4x162.6 mm)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --width 91.4 --height 162.6

echo "HD Wallpaper (162.6x91.4 mm)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --width 162.6 --height 91.4

echo "4K Wallpaper (325.1x182.9 mm)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --width 325.1 --height 182.9

echo "A4 Print (210x297 mm)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --width 210 --height 297

# 6. Distance Guide Variations
echo "--- Distance Guide Variations ---"
echo "Small/Dense focal (5000m)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -d 5000

echo "Medium/Focused downtown (10000m)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -d 10000

echo "Large metro view (default 18000m)"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -d 18000

# 7. Pen Plotter Output
echo "--- Pen Plotter Output ---"
echo "A3 plotter SVG, 0.3mm pen"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -d 5000 --format plotter --width 297 --height 420 --pen-width 0.3

echo "Plotter SVG, 0.5mm pen with sparse hatching"
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" -d 5000 --format plotter --width 300 --height 400 --pen-width 0.5 --hatch-spacing 1.5

# 8. Utility flags
echo "--- Utility Flags ---"
echo "Listing themes"
uv run python3 create_map_poster.py --list-themes

echo "Generating for ALL themes at once"
# We'll use a smaller distance to make it faster for testing
uv run python3 create_map_poster.py -c "Bengaluru" -C "India" --all-themes -d 10000

echo "===================================================="
echo "Done! Posters saved to posters/ directory."
echo "===================================================="
