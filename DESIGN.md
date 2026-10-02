---
name: Pace Explorer
description: The incumbent blue and green visual system for personal pace history.
colors:
  navy: "#1f4e78"
  chart-blue: "#4472c4"
  green: "#217346"
  ink: "#20364a"
  muted: "#5d6f7e"
  grid: "#dbe3e9"
  surface: "#f3f6f8"
  pale-blue: "#edf4fa"
  pale-green: "#edf7f0"
  error: "#962f32"
  focus: "#4472c4"
  white: "#ffffff"
  input-border: "#aebdca"
  primary-hover: "#195b36"
  primary-active: "#12462a"
  header-hover: "#32628c"
  header-active: "#153f62"
  live-green: "#75e3a0"
typography:
  brand:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1.375rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.02em"
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1.625rem"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.02em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1rem"
    fontWeight: 650
    lineHeight: 1.4
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: ".875rem"
    fontWeight: 600
    lineHeight: 1.5
  supporting:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: ".8125rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  small: "6px"
  control: "8px"
  table: "10px"
  panel: "12px"
  circle: "50%"
spacing:
  small: "8px"
  compact: "12px"
  standard: "16px"
  comfortable: "20px"
  panel: "24px"
  section: "28px"
  large: "32px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "11px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.small}"
    padding: "8px 2px"
  button-refresh:
    backgroundColor: "transparent"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "0"
    height: "44px"
    width: "44px"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 12px"
    width: "100%"
  select:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    width: "100%"
  account-navigation:
    textColor: "{colors.muted}"
  chart-panel:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel}"
  monthly-table:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.table}"
    width: "100%"
  status:
    backgroundColor: "{colors.pale-blue}"
    textColor: "{colors.navy}"
    rounded: "{rounded.control}"
    padding: "14px 16px"
---

# Design System: Pace Explorer

## Overview

**Creative North Star: "Pace Explorer"**

The existing icon and blue and green identity are the visual anchor. Navy carries the application name, blue carries the pace line, and green carries primary actions. The interface uses familiar forms, restrained headings, and a light blue-gray canvas to keep personal history readable.

The system is compact and flat. White data surfaces, fine separators, and clear labels establish hierarchy without decorative metric cards or raised effects. Account screens use the same controls and type as the dashboard. This document records the implementation in `viz/index.html`, `viz/styles.css`, and `viz/app.js`; it extends the incumbent identity rather than creating a new one.

**Key Characteristics:**
- Existing Pace Explorer icon and blue and green identity.
- Single UI font with sentence-case headings and labels.
- White data surfaces with quiet borders and no shadows.
- Explicit input labels, visible keyboard focus, and generous action targets.
- Tabular numerals and right-aligned numeric table columns.

## Colors

The palette combines navy and chart blue with a darker action green, supported by cool, low-contrast neutral surfaces.

### Primary
- **Navy:** application header, navigation actions, disclosure headings, and informational messages.
- **Chart Blue:** pace line and markers; the matching Focus token provides the keyboard outline and focused field border.
- **Header Hover / Header Active:** darker and lighter blue state surfaces for the refresh control.

### Secondary
- **Green:** primary buttons, input caret, and the current account-navigation state.
- **Primary Hover / Primary Active:** progressively darker green states for primary buttons.
- **Live Green:** the small sync indicator against the navy header.
- **Pale Green:** success-message surface.

### Tertiary
- **Error:** error-message text; error notices pair it with a pale red surface and red border defined by that component.

### Neutral
- **Ink:** default body, field, and numeric-value text.
- **Muted:** explanatory text, filter labels, account identity, and table headings.
- **Grid:** separators and borders around data surfaces.
- **Surface:** page canvas.
- **White:** controls and data surfaces; reversed header and primary-button text.
- **Pale Blue:** informational messages and table-heading surface.
- **Input Border:** the shared field and selector stroke.

### Named Rules

**The Data and Action Rule.** Use chart blue for the pace series and green for primary actions; preserve navy as the identity and navigation anchor.

**The Honest Status Rule.** The live green indicator belongs to a running import and stays paired with its record-count label. Last-update metadata represents a completed successful sync.

## Typography

**UI Font:** the platform UI stack recorded in the frontmatter. The application and chart share this family; no separate display face is used.

**Character:** practical and familiar, with moderately weighted headings and compact supporting text. Hierarchy comes from size, weight, and spacing rather than uppercase labels or decorative type.

### Hierarchy
- **Brand:** the application name in the header; reduces to (1.125rem) at the main narrow breakpoint and (1rem) at the smallest breakpoint.
- **Headline:** account and dashboard headings; reduces to (1.5rem) at the main narrow breakpoint.
- **Title:** section headings and fieldset legends.
- **Body:** page text and form inputs. Introductions and primary buttons use (.9375rem).
- **Label:** field labels and text actions. Filter labels and table headings use the smaller supporting size with a weight of (600).
- **Supporting:** field hints, chart notes, chart units, and table-year metadata. Header update metadata starts at (.75rem) and reduces to (.6875rem) on narrow screens.

### Named Rules

**The Numeric Clarity Rule.** Use tabular numerals for update timestamps, summary values, and data tables. Keep pace units intact and align numeric table columns to the right.

## Layout

The page is a vertical application shell with a sticky, full-width header and a centered main container capped at (1100px). Desktop main gutters are (32px); they reduce to (20px) at (720px) and (16px) at (380px). The header includes safe-area-aware gutters. Its brand sits at the left and refresh/update controls stay at the right.

Forms remain one column. The sign-in form is capped at (430px), account settings at (560px), and explanatory cleaning text at (70ch). Reused gaps and padding follow the frontmatter spacing scale, with larger section breaks rather than nested cards.

The dashboard has a three-column filter row: columns are (180px) wide on desktop, then share available width at the main narrow breakpoint. A bordered summary row follows. The chart surface comes before the monthly table and cleaning disclosure. Chart height changes from (360px) to (310px) on narrow screens; chart point labels are removed and alternating month ticks are suppressed there. Table scrolling is contained within its rounded wrapper.

Interactive text actions, refresh, selectors, and disclosure summaries have minimum targets of (44px); primary buttons and form inputs have minimum heights of (48px).

## Elevation & Depth

The implementation uses no box shadows. Depth comes from the blue-gray page canvas, white data surfaces, pale status surfaces, and thin borders. The navy header is a persistent visual anchor; its green top rule is part of that header treatment. Keyboard focus uses an outline rather than an elevation effect.

### Named Rules

**The Flat Boundary Rule.** Separate data and form regions with tone, spacing, and fine borders. Keep surfaces flat at rest and during interaction.

## Shapes

Controls and notices use gently rounded corners. Smaller text actions use the small radius, inputs and buttons use the control radius, the table wrapper uses the table radius, and the chart surface uses the panel radius. Borders are consistently thin (1px) except the existing header's (3px) green top rule. The brand icon uses rounded corners and scales down with the header. The sync indicator is circular; action icons are inline stroked SVGs.

## Components

### Buttons

Primary actions are solid green with white text, a matching thin border, and a minimum height of (48px). Hover and active states darken the green. Sign-in and signup actions fill the form width; settings actions use their natural width.

Text actions are navy and transparent with a minimum height of (44px). Hover adds an underline; active and current-page states use green. The refresh button is a square (44px) outlined control with white iconography in the navy header. Its hover, active, and busy surfaces use the header blue state colors. Disabled buttons reduce opacity to (.6); busy controls use a wait cursor.

All keyboard-focusable controls inherit the visible outline (3px, offset 3px). The header refresh control uses a pale green focus outline for contrast against navy. State transitions use (.16s ease-out), and reduced-motion preferences remove them.

### Inputs / Fields

Inputs and the session textarea use white surfaces, the shared field stroke, and the control radius. Labels are visible above fields and hints below. Inputs darken their border to navy on hover and use chart blue on keyboard focus. Selectors follow the same stroke and radius with a smaller minimum height. The textarea keeps vertical resizing available.

### Navigation

The brand icon and name anchor the header. Update metadata is right-aligned beside the refresh action on both desktop and mobile. Account identity and text actions sit in a separate horizontal row with a bottom divider; long account names may wrap without widening the page. Back navigation uses a stroked arrow and text.

### Cards / Containers

The chart is the principal white panel: a thin grid-colored border, panel-radius corners, and spacious internal padding. On narrow screens its padding contracts and its heading and units stack. Authentication and account forms are unboxed against the page canvas.

### Data Table

The monthly table uses a pale blue header, white rows, thin horizontal separators, and tabular numerals. Its first column is left-aligned and numeric columns are right-aligned. Months outside the selected interval use a quieter neutral row treatment. The rounded wrapper contains horizontal scrolling.

### Status and Sync

Inline notices share a bordered, rounded format. Informational messages use pale blue and navy, success messages use pale green and dark green, and errors use pale red and Error text. They allow long text to wrap.

The top-bar sync label includes a live green dot only while the import is running. The dot flashes over (1.2s ease-in-out); reduced-motion preferences leave it steady. The dot supplements the loading label and count rather than carrying status alone.

### Disclosures

Cleaning details and Garmin verification use native disclosures with navy summary text, a minimum target of (44px), and quiet separators. Cleaning-summary hover changes the text to green. Details remain secondary to the chart and account fields.

## Do's and Don'ts

### Do:
- **Do** preserve the existing Pace Explorer icon and blue and green identity.
- **Do** reuse the shared field, button, border, and spacing treatments across account and dashboard screens.
- **Do** retain visible labels, keyboard outlines, and the established minimum action targets.
- **Do** keep timestamps and data values legible with tabular numerals and intact units.
- **Do** pair live sync animation with a running import, a visible count, and reduced-motion behavior.

### Don't:
- **Don't** replace the established palette or identity asset when extending the interface.
- **Don't** add ornamental metric cards to the dashboard's existing summary row.
- **Don't** use a flashing status indicator for an idle or completed state.
- **Don't** turn chart-specific legacy neutral colors into shared tokens without reconciling them with the reusable palette.
