# Tasks

## 1. CLI

- [x] 1.1 Remove the `MAX_SIZE_MM` clamping. Add `png_pixels`, `max_png_dpi`, `MAX_PNG_PIXELS` (200 MP) and `MAX_PNG_SIDE` (65,535), and reject oversized PNGs before any download with the pixel size and the highest fitting dpi. Verify in `test_cli.py`: 1000 × 1500 mm PNG at 300 dpi exits non-zero with "293 dpi" in the message and no download; the same at `--dpi 293` renders (checked with the size helper, not a full render); 600 × 900 mm SVG and PDF are accepted at exactly that size (SVG root `width`/`height`, PDF MediaBox).
- [x] 1.2 Update the `--width`/`--height` help, `print_examples`, the README option tables and the resolution guide (no mm limit; PNG pixel limit). Verify with `--help`.

## 2. Web server

- [x] 2.1 Drop the print mm check from `validate_location`. Add `CustomizeConfig.dpi` (default 300, > 0) and the PNG pixel-limit check in `validate_customize` against the loaded size (error on `dpi` naming the highest dpi). Export passes `--dpi` for PNG. Verify with web tests: an 841 × 1189 print load is accepted, a PNG export over the limit gets 422 on `dpi`, an SVG export of the same size is accepted, and preview commands keep their own dpi. (The limit maths lives in the shared `poster_size.py` used by both the CLI and the server, so no separate agreement test is needed.)

## 3. Web frontend

- [x] 3.1 Update the workflow card and size hint texts (no 500 mm). Add the PNG dpi field (print workflow, PNG only) with the live pixel size, a warning above 100 MP, and an error with a "Use N dpi" button over the limit, blocking export. Verify in the browser with a 1000 × 1500 mm print session: the error shows 293 dpi, the button fixes it, and switching to SVG hides the field.

## 4. Integration

- [x] 4.1 Run the full test suite and flake8, and check both are clean.
- [x] 4.2 Rebuild and restart the Docker Compose container, and verify the new UI on port 8001.
