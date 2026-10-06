"""
Generate the bold icon sets from the regular classic and modern icons.

The regular icons are read from const.py (FRACTION_ICONS_NEW) and
frontend/afvalbeheer-icons.js (ICONS and the dark/light theme variants). The bold
versions are written between the GENERATED BOLD ICONS markers in the same files.

Run this after changing any of the regular icons:

    python3 -m venv /tmp/iconvenv
    /tmp/iconvenv/bin/pip install shapely svgelements
    /tmp/iconvenv/bin/python scripts/generate_bold_icons.py
"""
import base64
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.affinity import scale as scale_geometry, translate
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from svgelements import Close, Line, Move, Path as SvgPath

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "afvalbeheer"
CONST_FILE = ROOT / "const.py"
JS_FILE = ROOT / "frontend" / "afvalbeheer-icons.js"

# Extra line thickness, in units of a 141.7 wide viewBox (regular lines are about 3-3.7 wide)
EXTRA_WIDTH = 4.0
MODERN_EXTRA_WIDTH = 2.4
REFERENCE_WIDTH = 141.7

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
ET.register_namespace("serif", "http://www.serif.com/")
SHAPES = {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
INHERITED = ("fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap")
DATA_URI_PREFIX = "data:image/svg+xml;base64,"


# --- Modern icons: thicken strokes, and outline filled shapes in their own color ---

def _local(tag):
    return tag.split("}")[-1]


def _parse_declarations(text):
    declarations = {}
    for part in (text or "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            declarations[key.strip()] = value.strip()
    return declarations


def _class_rules(root):
    rules = {}
    for style in root.iter("{%s}style" % SVG_NS):
        for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.text or ""):
            for selector in selectors.split(","):
                selector = selector.strip()
                if selector.startswith("."):
                    rules.setdefault(selector[1:], {}).update(_parse_declarations(body))
    return rules


def _own_properties(element, rules):
    props = {key: element.get(key) for key in INHERITED if element.get(key) is not None}
    for cls in (element.get("class") or "").split():
        props.update({k: v for k, v in rules.get(cls, {}).items() if k in INHERITED})
    props.update({k: v for k, v in _parse_declarations(element.get("style")).items() if k in INHERITED})
    return props


def _stroke_width(value):
    match = re.match(r"([\d.]+)", value or "")
    return float(match.group(1)) if match else 1.0


def _visible(paint):
    return paint is not None and paint.strip().lower() not in ("none", "transparent")


def bold_modern_svg(svg_text):
    root = ET.fromstring(svg_text)
    view_box = [float(x) for x in re.split(r"[\s,]+", root.get("viewBox").strip())]
    extra = MODERN_EXTRA_WIDTH * view_box[2] / REFERENCE_WIDTH
    rules = _class_rules(root)

    def walk(element, inherited):
        props = {**inherited, **_own_properties(element, rules)}
        if _local(element.tag) in SHAPES:
            style = _parse_declarations(element.get("style"))
            if _visible(props.get("stroke")):
                style["stroke-width"] = "%.2f" % (_stroke_width(props.get("stroke-width")) + extra)
            elif _visible(props.get("fill", "#000")):
                style["stroke"] = props.get("fill", "#000")
                style["stroke-width"] = "%.2f" % extra
                style["stroke-linejoin"] = "round"
            element.set("style", ";".join("%s:%s" % item for item in style.items()))
        for child in element:
            if _local(child.tag) not in ("style", "defs", "title"):
                walk(child, props)

    walk(root, {})
    # The frontend recognizes bold pictures by the "-bold" id suffix
    if root.get("id"):
        root.set("id", root.get("id") + "-bold")
    return ET.tostring(root, encoding="unicode")


def bold_modern_base64(b64):
    svg = base64.b64decode(b64).decode()
    return base64.b64encode(bold_modern_svg(svg).encode()).decode()


# --- Classic icons: grow the filled shape outward ---

def _path_to_geometry(d, step):
    rings = []
    for subpath in SvgPath(d).as_subpaths():
        points = []
        for segment in subpath:
            if isinstance(segment, (Move, Line, Close)):
                if segment.end is not None:
                    points.append((segment.end.x, segment.end.y))
            else:
                count = max(4, int(segment.length() / step))
                points += [(segment.point(i / count).x, segment.point(i / count).y) for i in range(1, count + 1)]
        if len(points) >= 3:
            ring = Polygon(points).buffer(0)
            if not ring.is_empty:
                rings.append(ring)
    # Even-odd fill: every ring toggles coverage
    geometry = rings[0]
    for ring in rings[1:]:
        geometry = geometry.symmetric_difference(ring)
    return geometry


def _geometry_to_path(geometry, decimals):
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    number = "%%.%df" % decimals
    parts = []
    for polygon in polygons:
        polygon = orient(polygon, 1.0)
        for ring in [polygon.exterior] + list(polygon.interiors):
            coords = list(ring.coords)[:-1]
            parts.append("M" + " L".join(number % x + " " + number % y for x, y in coords) + " Z")
    return " ".join(parts)


def _fit_to_bounds(geometry, bounds):
    """Scale the grown shape back into the original outer bounds, so it is not clipped by the viewBox."""
    min_x, min_y, max_x, max_y = geometry.bounds
    target_min_x, target_min_y, target_max_x, target_max_y = bounds
    factor = min((target_max_x - target_min_x) / (max_x - min_x), (target_max_y - target_min_y) / (max_y - min_y))
    center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    target_center = ((target_min_x + target_max_x) / 2, (target_min_y + target_max_y) / 2)
    geometry = scale_geometry(geometry, xfact=factor, yfact=factor, origin=center)
    return translate(geometry, target_center[0] - center[0], target_center[1] - center[1])


def bold_classic_path(d, view_box):
    width = float(view_box.split()[2])
    scale = width / REFERENCE_WIDTH
    geometry = _path_to_geometry(d, 0.4 * scale)
    bold = geometry.buffer(EXTRA_WIDTH / 2 * scale, join_style="mitre", mitre_limit=2.0)
    bold = _fit_to_bounds(bold, geometry.bounds)
    bold = bold.simplify(0.05 * scale, preserve_topology=True)
    return _geometry_to_path(bold, 1 if width > 1000 else 2)


# --- Reading and writing the source files ---

def _replace_generated(text, begin, end, content):
    start = text.index(begin) + len(begin)
    stop = text.index(end)
    return text[:start] + "\n" + content + text[stop:]


def generate_const(const_text):
    block = const_text[const_text.index("FRACTION_ICONS_NEW = {"):const_text.index("FRACTION_ICONS_NEW.update")]
    icons = re.findall(r"'([\w-]+)': '%s([A-Za-z0-9+/=]+)'" % re.escape(DATA_URI_PREFIX), block)
    aliases = re.findall(r"'([\w-]+)': FRACTION_ICONS_NEW\['([\w-]+)'\]", const_text)

    lines = ["FRACTION_ICONS_NEW_BOLD = {"]
    for name, b64 in icons:
        lines.append("    '%s': '%s%s'," % (name, DATA_URI_PREFIX, bold_modern_base64(b64)))
    lines += ["}", "", "FRACTION_ICONS_NEW_BOLD.update({"]
    for alias, target in aliases:
        lines.append("    '%s': FRACTION_ICONS_NEW_BOLD['%s']," % (alias, target))
    lines += ["})", ""]
    return _replace_generated(
        const_text,
        "# BEGIN GENERATED BOLD ICONS (scripts/generate_bold_icons.py)",
        "# END GENERATED BOLD ICONS",
        "\n".join(lines),
    )


def generate_js(js_text):
    icons = json.loads(re.search(r"const ICONS = (\{.*?\n  \});", js_text, re.S).group(1))
    themed = re.findall(r'const (\w+_(?:LIGHT|DARK)) = "([A-Za-z0-9+/=]+)";', js_text)

    bold_icons = {
        name: {"path": bold_classic_path(icon["path"], icon["viewBox"]), "viewBox": icon["viewBox"]}
        for name, icon in icons.items()
    }
    lines = ["  const ICONS_BOLD = %s;" % json.dumps(bold_icons, indent=2).replace("\n", "\n  ")]
    for name, b64 in themed:
        lines.append('  const %s_BOLD = "%s";' % (name, bold_modern_base64(b64)))
    lines.append("")
    return _replace_generated(
        js_text,
        "  // BEGIN GENERATED BOLD ICONS (scripts/generate_bold_icons.py)",
        "  // END GENERATED BOLD ICONS",
        "\n".join(lines),
    )


def main():
    CONST_FILE.write_text(generate_const(CONST_FILE.read_text()))
    JS_FILE.write_text(generate_js(JS_FILE.read_text()))
    print("Updated %s and %s" % (CONST_FILE.name, JS_FILE.name))


if __name__ == "__main__":
    main()
