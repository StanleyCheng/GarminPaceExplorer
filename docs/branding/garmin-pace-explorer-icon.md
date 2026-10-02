# GarminPaceExplorer icon

The selected Garmin runner and activity-trend icon was supplied by the user,
then extracted with the built-in imagegen tool on 2026-10-02. The approved
transparent master is in `assets/branding/garmin-pace-explorer-master.png`.

Browser exports in `viz/` use the same artwork at 16px, 32px, and 48px (ICO).
The Apple touch icon is 180px and `viz/icons/garmin-pace-explorer.png` is 512px.
Exports only resize or encode the approved artwork and preserve its alpha
channel and rounded corners. The dashboard header, browser favicons, and
Safari bookmark/home-screen icon all use this artwork. Icon URLs include
`v=garmin-runner-1` to refresh previously cached icons.

## Extraction prompt

```text
Use case: background-extraction
Asset type: transparent PNG app icon cutout
Input image: edit target, the supplied Garmin running/trend rounded-square icon.
Primary request: Extract only the existing rounded-square icon and all of its interior artwork. Remove everything outside the icon's outer rounded corners.
Constraints: Preserve the existing icon exactly: its rounded-square silhouette, blue diagonal GARMIN header with the registered trademark symbol, dark lower surface, white running figure, blue rising graph line and dots, and blue bars. Preserve all relative positions, colors, proportions, lettering, shading, and interior texture. Do not redesign, add, remove, or change any element inside the rounded-square icon.
Background extraction: Make the entire area outside the rounded-square perimeter truly transparent, including the black outer corners, white residue beneath the bottom corners, cyan fringe and stray pixels outside the top edge, and any surrounding shadow. Keep the dark icon interior opaque. Cleanly antialias the outer rounded perimeter without a cyan or white halo. Crop closely to the icon's outer bounding box, keeping its complete rounded corners and a very small transparent margin. Deliver only one clean isolated icon on actual transparent alpha, no checkerboard baked into the pixels, no added background, no mockup or extra border.
```

## Final refinement prompt

```text
Use case: background-extraction
Edit target: the supplied transparent Garmin icon cutout.
Make only one correction: clean the outer alpha matte. Remove every stray cyan pixel, cyan fringe, fleck, halo, or shadow outside the rounded-square icon. In particular, the tiny cyan fleck above the center of the top edge and the uneven cyan residue along the top and left edge must be completely removed. Produce a smooth, clean, antialiased rounded-square boundary. A narrow empty transparent margin must separate the icon from every canvas edge; the entire outermost row and column on all sides must be fully transparent. Everything inside the icon silhouette must be opaque, with only edge antialiasing semi-transparent.
Preserve every interior element exactly as in the supplied cutout: GARMIN lettering and registration mark, diagonal blue header, dark surface, white runner, line chart, dots, six bars, colors, positions and textures. Do not change, redraw, simplify, rearrange, or restyle the artwork. Do not introduce any background. Output a genuine transparent PNG.
```
