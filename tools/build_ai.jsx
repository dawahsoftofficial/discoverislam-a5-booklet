// Build a layered Illustrator file from the editable print PDF (run by build_print_pdf.py --ai).
// arguments: [pdf path, output .ai path, page count]
//
// One artboard per page (210x148mm trim, laid out 4 across), and five layers, bottom to top:
//   Backgrounds  full-bleed fills behind everything
//   Photos       photos and logos
//   Shapes       cards, icons, lines, overlays (anything vector above the photos)
//   Text         live text
//   Crop marks
// Each page's content sits in a "Page N" group per layer, clipped to that page's 3mm bleed.
// Pages are placed and embedded straight into the new file (no copying between documents, which
// loses gradients and is slow). Groups with transparency are kept whole so their look survives.
// Progress is appended to <output>.log.

app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;

var MM = 72 / 25.4;
var SRC = new File(arguments[0]), OUT = new File(arguments[1]), PAGES = parseInt(arguments[2], 10);
var LOG = new File(arguments[1] + ".log");
var TRIM_W = 210 * MM, TRIM_H = 148 * MM, OFF = 10 * MM, BLEED = 3 * MM, MARK_GAP = 3 * MM, MARK_LEN = 6 * MM;
var COLS = 4, PITCH_X = 240 * MM, PITCH_Y = 178 * MM;
var LAYERS = ["Backgrounds", "Photos", "Shapes", "Text", "Crop marks"];

function log(s) { LOG.open("a"); LOG.writeln(new Date().toTimeString().substr(0, 8) + " " + s); LOG.close(); }
LOG.open("w"); LOG.close();

var master = app.documents.add(DocumentColorSpace.CMYK, TRIM_W, TRIM_H);
var layer = {};
master.layers[0].name = LAYERS[0];
layer[LAYERS[0]] = master.layers[0];
for (var l = 1; l < LAYERS.length; l++) { var nl = master.layers.add(); nl.name = LAYERS[l]; layer[LAYERS[l]] = nl; }
var importLayer = master.layers.add(); importLayer.name = "_import";
var REG = new CMYKColor(); REG.cyan = REG.magenta = REG.yellow = REG.black = 100;

function area(b) { return Math.max(0, b[2] - b[0]) * Math.max(0, b[1] - b[3]); }
function intersects(a, b) { return a[0] < b[2] && a[2] > b[0] && a[3] < b[1] && a[1] > b[3]; }
function overlap(a, b) { return [Math.max(a[0], b[0]), Math.min(a[1], b[1]), Math.min(a[2], b[2]), Math.max(a[3], b[3])]; }
function hasType(g, type) {
  for (var i = 0; i < g.pageItems.length; i++) {
    var it = g.pageItems[i];
    if (it.typename === type || (it.typename === "GroupItem" && hasType(it, type))) return true;
  }
  return false;
}
function clipRect(g) {
  for (var i = 0; i < g.pageItems.length; i++) if (g.pageItems[i].clipping) return g.pageItems[i].geometricBounds;
  return g.geometricBounds;
}
function plain(it) { return it.opacity >= 99.9 && it.blendingMode === BlendModes.NORMAL; }
function line(g, x1, y1, x2, y2) {
  var p = g.pathItems.add(); p.setEntirePath([[x1, y1], [x2, y2]]);
  p.filled = false; p.stroked = true; p.strokeWidth = 0.25; p.strokeColor = REG;
}

var opts = app.preferences.PDFFileOptions;
opts.pDFCropToBox = PDFBoxType.PDFMEDIABOX;
var summary = [];

for (var p = 1; p <= PAGES; p++) {
  var col = (p - 1) % COLS, row = Math.floor((p - 1) / COLS);
  var sx = col * PITCH_X, sy = -row * PITCH_Y;                       // sheet top-left
  var trim = [sx + OFF, sy - OFF, sx + OFF + TRIM_W, sy - OFF - TRIM_H];
  var bleed = [trim[0] - BLEED, trim[1] + BLEED, trim[2] + BLEED, trim[3] - BLEED];
  var bleedArea = area(bleed);
  if (p === 1) master.artboards[0].artboardRect = trim; else master.artboards.add(trim);
  master.artboards[p - 1].name = "Page " + p;

  opts.pageToOpen = p;
  var placed = importLayer.placedItems.add();
  placed.file = SRC;
  placed.position = [sx, sy];
  placed.embed();

  var group = {}, count = {};
  for (var k = 0; k < LAYERS.length; k++) {
    group[LAYERS[k]] = layer[LAYERS[k]].groupItems.add();
    group[LAYERS[k]].name = "Page " + p;
    count[LAYERS[k]] = 0;
  }
  var seenPhoto = false;
  function put(item, name) { item.move(group[name], ElementPlacement.PLACEATBEGINNING); count[name]++; }
  function walk(container) {
    var items = container.pageItems;
    for (var i = items.length - 1; i >= 0; i--) {                     // bottom to top
      var it = items[i];
      if (it.clipping) continue;
      var vb = it.visibleBounds, t = it.typename;
      if (t === "PathItem" && it.stroked && !it.filled && it.strokeWidth <= 0.5 && !intersects(vb, trim)) continue; // old marks
      if (it.hidden || !intersects(vb, bleed)) continue;              // clipped out of view in the PDF
      if (t === "GroupItem") {
        // open up plain groups and page-sized clips (replaced by the per-page bleed clip below);
        // anything with transparency stays whole so its appearance survives
        if (plain(it) && (!it.clipped || area(clipRect(it)) >= 0.7 * bleedArea)) { walk(it); continue; }
        if (hasType(it, "RasterItem") || hasType(it, "PlacedItem")) { put(it, "Photos"); seenPhoto = true; }
        else if (hasType(it, "TextFrame")) put(it, "Text");
        else put(it, (!seenPhoto && area(overlap(vb, bleed)) >= 0.8 * bleedArea) ? "Backgrounds" : "Shapes");
      } else if (t === "TextFrame") {
        put(it, "Text");
      } else if (t === "RasterItem" || t === "PlacedItem") {
        put(it, "Photos"); seenPhoto = true;
      } else if (!seenPhoto && area(overlap(vb, bleed)) >= 0.8 * bleedArea) {
        put(it, "Backgrounds");
      } else {
        put(it, "Shapes");
      }
    }
  }
  walk(importLayer);
  while (importLayer.pageItems.length) importLayer.pageItems[0].remove();

  var marks = group["Crop marks"], L = trim[0], T = trim[1], R = trim[2], B = trim[3];
  line(marks, L, T + MARK_GAP, L, T + MARK_GAP + MARK_LEN); line(marks, R, T + MARK_GAP, R, T + MARK_GAP + MARK_LEN);
  line(marks, L, B - MARK_GAP, L, B - MARK_GAP - MARK_LEN); line(marks, R, B - MARK_GAP, R, B - MARK_GAP - MARK_LEN);
  line(marks, L - MARK_GAP, T, L - MARK_GAP - MARK_LEN, T); line(marks, L - MARK_GAP, B, L - MARK_GAP - MARK_LEN, B);
  line(marks, R + MARK_GAP, T, R + MARK_GAP + MARK_LEN, T); line(marks, R + MARK_GAP, B, R + MARK_GAP + MARK_LEN, B);
  count["Crop marks"] = 8;

  var info = "page " + p + ":";
  for (var k2 = 0; k2 < LAYERS.length; k2++) {
    var lname = LAYERS[k2], g = group[lname];
    if (count[lname] === 0) { g.remove(); continue; }
    if (lname !== "Crop marks") {                                      // clip each page to its bleed
      var r = g.pathItems.rectangle(bleed[1], bleed[0], bleed[2] - bleed[0], bleed[1] - bleed[3]);
      r.move(g, ElementPlacement.PLACEATBEGINNING);
      g.clipped = true;
    }
    info += " " + lname + "=" + count[lname];
  }
  summary.push(info);
  log(info);
}
importLayer.remove();

var save = new IllustratorSaveOptions();
save.pdfCompatible = true;
save.embedICCProfile = true;
save.compressed = true;
master.saveAs(OUT, save);
master.close(SaveOptions.DONOTSAVECHANGES);
log("saved " + OUT.fsName);
summary.join("\n");
