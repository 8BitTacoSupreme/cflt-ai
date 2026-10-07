#!/usr/bin/env bash
# Renders the mermaid art assets for the Event Handler Design Patterns deck to SVG.
# Vector out, so they drop into PowerPoint / Google Slides / Keynote without resampling.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p svg

# Palette shared with the hand-authored Visio-style assets, so the deck reads as one system.
cat > mermaid-config.json <<'EOF'
{
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, Segoe UI, Helvetica Neue, sans-serif",
    "fontSize": "15px",
    "primaryColor": "#EAF1FA",
    "primaryTextColor": "#173A6C",
    "primaryBorderColor": "#0074E4",
    "lineColor": "#5A6572",
    "secondaryColor": "#E3F5F4",
    "secondaryBorderColor": "#00A6A0",
    "tertiaryColor": "#F4F6F8",
    "tertiaryBorderColor": "#5A6572",
    "clusterBkg": "#F7F9FB",
    "clusterBorder": "#5A6572",
    "edgeLabelBackground": "#FFFFFF",
    "noteBkgColor": "#FDF3DC",
    "noteBorderColor": "#F2A900",
    "noteTextColor": "#173A6C"
  },
  "flowchart": { "curve": "basis", "nodeSpacing": 45, "rankSpacing": 55, "htmlLabels": true },
  "sequence": { "actorMargin": 60, "noteFontWeight": "500" }
}
EOF

for f in mmd/*.mmd; do
  base="$(basename "$f" .mmd)"
  echo "rendering ${base}"
  npx -y @mermaid-js/mermaid-cli@11 \
    -i "$f" -o "svg/${base}.svg" \
    -c mermaid-config.json -b transparent --quiet
done

echo "done — $(ls svg/*.svg 2>/dev/null | wc -l | tr -d ' ') svg files in svg/"
