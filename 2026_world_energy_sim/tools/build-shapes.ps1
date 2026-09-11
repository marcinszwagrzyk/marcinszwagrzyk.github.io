# Regenerate js/data/world-shapes.js from Natural Earth 1:50m admin-0 countries.
#
# The page has to stay a single self-contained file, so the boundaries ship as
# source: rings are Douglas-Peucker simplified, quantised to 0.01 deg and
# delta-encoded into strings (polyline-style varints over a JS-safe alphabet).
# Two levels of detail are emitted - the renderer draws `coarse` when zoomed out.
#
#     powershell -ExecutionPolicy Bypass -File tools/build-shapes.ps1
#
# The geometry work runs in C# (Add-Type): 240 features / ~1.4M coordinate pairs
# is far too much for PowerShell loops.

param(
  [double]$TolFine   = 0.025,   # degrees; ~2 px at max zoom
  [double]$TolCoarse = 0.35,
  [double]$MinFine   = 0.22,    # drop islands smaller than this (degrees across)
  [double]$MinCoarse = 1.2
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$src  = Join-Path $env:TEMP 'ne_50m_admin_0_countries.geojson'
$out  = Join-Path $root 'js\data\world-shapes.js'

if (-not (Test-Path $src)) {
  Write-Host 'downloading Natural Earth 1:50m admin-0 ...'
  $ProgressPreference = 'SilentlyContinue'
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -OutFile $src `
    -Uri 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson'
}

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

public static class ShapeBuild {
  // JS-safe base-64 alphabet: no quote, backslash, or the | ~ separators.
  const string ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-";

  public class Ring { public string Iso; public double[] X; public double[] Y; }

  // ---- geometry ------------------------------------------------------------

  // Perpendicular distance, longitudes scaled by cos(lat) so the tolerance means
  // the same thing in Murmansk as in Mombasa.
  static double PerpDist(double px, double py, double ax, double ay, double bx, double by, double kx) {
    double dx = (bx - ax) * kx, dy = by - ay;
    double len2 = dx * dx + dy * dy;
    double ex = (px - ax) * kx, ey = py - ay;
    if (len2 <= 0) return Math.Sqrt(ex * ex + ey * ey);
    double t = (ex * dx + ey * dy) / len2;
    if (t < 0) t = 0; else if (t > 1) t = 1;
    double qx = ex - t * dx, qy = ey - t * dy;
    return Math.Sqrt(qx * qx + qy * qy);
  }

  static void DP(double[] x, double[] y, int i, int j, double tol, double kx, bool[] keep) {
    var stack = new Stack<int[]>();
    stack.Push(new int[] { i, j });
    while (stack.Count > 0) {
      int[] seg = stack.Pop();
      int a = seg[0], b = seg[1];
      double worst = -1; int wi = -1;
      for (int k = a + 1; k < b; k++) {
        double d = PerpDist(x[k], y[k], x[a], y[a], x[b], y[b], kx);
        if (d > worst) { worst = d; wi = k; }
      }
      if (worst > tol) {
        keep[wi] = true;
        stack.Push(new int[] { a, wi });
        stack.Push(new int[] { wi, b });
      }
    }
  }

  // A closed ring has first == last, which makes a single DP pass degenerate;
  // split it at the vertex farthest from the start and simplify both halves.
  static List<double[]> Simplify(double[] x, double[] y, double tol) {
    int n = x.Length;
    if (n < 4) return null;
    double kx = Math.Cos(Avg(y) * Math.PI / 180.0);
    if (kx < 0.15) kx = 0.15;

    int far = 0; double best = -1;
    for (int k = 1; k < n; k++) {
      double dx = (x[k] - x[0]) * kx, dy = y[k] - y[0];
      double d = dx * dx + dy * dy;
      if (d > best) { best = d; far = k; }
    }
    var keep = new bool[n];
    keep[0] = true; keep[n - 1] = true; keep[far] = true;
    DP(x, y, 0, far, tol, kx, keep);
    DP(x, y, far, n - 1, tol, kx, keep);

    var pts = new List<double[]>();
    for (int k = 0; k < n; k++) if (keep[k]) pts.Add(new double[] { x[k], y[k] });
    return pts.Count >= 4 ? pts : null;
  }

  static double Avg(double[] v) { double s = 0; for (int i = 0; i < v.Length; i++) s += v[i]; return s / v.Length; }

  // ---- encoding ------------------------------------------------------------
  static void Varint(StringBuilder sb, int v) {
    uint z = (uint)((v << 1) ^ (v >> 31));
    while (z >= 32) { sb.Append(ALPHA[(int)(32 | (z & 31))]); z >>= 5; }
    sb.Append(ALPHA[(int)z]);
  }

  static string Encode(List<double[]> pts, out int kept) {
    var sb = new StringBuilder();
    int px = 0, py = 0; kept = 0;
    for (int i = 0; i < pts.Count; i++) {
      int qx = (int)Math.Round(pts[i][0] * 100.0);
      int qy = (int)Math.Round(pts[i][1] * 100.0);
      if (i > 0 && qx == px && qy == py) continue;      // quantisation collapsed it
      Varint(sb, qx - px); Varint(sb, qy - py);
      px = qx; py = qy; kept++;
    }
    return kept >= 4 ? sb.ToString() : null;
  }

  // ---- geojson -------------------------------------------------------------
  static string Prop(string chunk, string key) {
    string tag = "\"" + key + "\":\"";
    int i = chunk.IndexOf(tag, StringComparison.Ordinal);
    if (i < 0) return null;
    i += tag.Length;
    int j = chunk.IndexOf('"', i);
    string v = chunk.Substring(i, j - i);
    return (v == "-99" || v.Length != 3) ? null : v;
  }

  // [[x,y],[x,y],...] starting at its '['
  static Ring ParseRing(string s, ref int i, string iso) {
    while (s[i] != '[') i++;
    i++;
    var xs = new List<double>(); var ys = new List<double>();
    while (true) {
      while (s[i] != '[' && s[i] != ']') i++;
      if (s[i] == ']') { i++; break; }
      i++;
      int c = i; while (s[c] != ',') c++;
      xs.Add(double.Parse(s.Substring(i, c - i), CultureInfo.InvariantCulture));
      i = c + 1;
      c = i; while (s[c] != ']') c++;
      ys.Add(double.Parse(s.Substring(i, c - i), CultureInfo.InvariantCulture));
      i = c + 1;
    }
    return new Ring { Iso = iso, X = xs.ToArray(), Y = ys.ToArray() };
  }

  // [ exterior, hole, ... ] - holes (Lesotho, San Marino, ...) are dropped:
  // those countries are their own feature anyway.
  static void ParsePolygon(string s, ref int i, string iso, List<Ring> outp) {
    while (s[i] != '[') i++;
    i++;
    int child = 0;
    while (true) {
      while (s[i] == ',' || s[i] == ' ') i++;
      if (s[i] == ']') { i++; return; }
      Ring r = ParseRing(s, ref i, iso);
      if (child == 0) outp.Add(r);
      child++;
    }
  }

  static void ParseMulti(string s, ref int i, string iso, List<Ring> outp) {
    while (s[i] != '[') i++;
    i++;
    while (true) {
      while (s[i] == ',' || s[i] == ' ') i++;
      if (s[i] == ']') { i++; return; }
      ParsePolygon(s, ref i, iso, outp);
    }
  }

  public static string Run(string jsonPath, string outPath, double tolFine, double tolCoarse, double minFine, double minCoarse) {
    string s = File.ReadAllText(jsonPath, Encoding.UTF8);
    var parts = s.Split(new string[] { "\"geometry\"" }, StringSplitOptions.None);
    var rings = new List<Ring>();

    for (int f = 1; f < parts.Length; f++) {
      string props = parts[f - 1];
      string iso = Prop(props, "ISO_A3_EH") ?? Prop(props, "ISO_A3") ?? Prop(props, "ADM0_A3") ?? "---";
      string geom = parts[f];
      int c = geom.IndexOf("\"coordinates\"", StringComparison.Ordinal);
      if (c < 0) continue;
      int i = c;
      // a bare Polygon nests one level less than a MultiPolygon
      if (geom.Contains("\"MultiPolygon\"")) ParseMulti(geom, ref i, iso, rings);
      else ParsePolygon(geom, ref i, iso, rings);
    }

    var sbF = new StringBuilder(); var sbC = new StringBuilder();
    int nF = 0, nC = 0, ptF = 0, ptC = 0;
    foreach (var r in rings) {
      double minx = double.MaxValue, maxx = -double.MaxValue, miny = double.MaxValue, maxy = -double.MaxValue;
      for (int k = 0; k < r.X.Length; k++) {
        if (r.X[k] < minx) minx = r.X[k]; if (r.X[k] > maxx) maxx = r.X[k];
        if (r.Y[k] < miny) miny = r.Y[k]; if (r.Y[k] > maxy) maxy = r.Y[k];
      }
      double kx = Math.Cos((miny + maxy) / 2 * Math.PI / 180.0);
      double size = Math.Max((maxx - minx) * Math.Max(kx, 0.15), maxy - miny);

      for (int lod = 0; lod < 2; lod++) {
        double tol = lod == 0 ? tolFine : tolCoarse;
        double min = lod == 0 ? minFine : minCoarse;
        if (size < min) continue;
        var pts = Simplify(r.X, r.Y, tol);
        if (pts == null) continue;
        int kept;
        string enc = Encode(pts, out kept);
        if (enc == null) continue;
        var sb = lod == 0 ? sbF : sbC;
        if (sb.Length > 0) sb.Append('|');
        sb.Append(r.Iso).Append('~').Append(enc);
        if (lod == 0) { nF++; ptF += kept; } else { nC++; ptC += kept; }
      }
    }

    var js = new StringBuilder();
    js.Append("/**\n * Country boundaries - Natural Earth 1:50m admin-0, simplified and packed.\n");
    js.Append(" * Generated by tools/build-shapes.ps1 - do not edit by hand.\n *\n");
    js.Append(" * Each ring is \"ISO3~<varints>\": zig-zag deltas of lon/lat at 0.01 deg,\n");
    js.Append(" * 5 bits per character over a JS-safe alphabet. LAND is drawn at full\n");
    js.Append(" * detail, LAND_LOW when the view is zoomed out.\n */\n\n");
    js.Append("const SHAPE_ALPHA = '").Append(ALPHA).Append("';\n\n");
    js.Append("function decodeShapes(blob) {\n");
    js.Append("  const idx = new Int8Array(128);\n");
    js.Append("  for (let i = 0; i < SHAPE_ALPHA.length; i++) idx[SHAPE_ALPHA.charCodeAt(i)] = i;\n");
    js.Append("  return blob.split('|').map(chunk => {\n");
    js.Append("    const iso = chunk.slice(0, 3);\n");
    js.Append("    const s = chunk, ring = [];\n");
    js.Append("    let i = 4, lon = 0, lat = 0;\n");
    js.Append("    while (i < s.length) {\n");
    js.Append("      let r = 0, sh = 0, b;\n");
    js.Append("      do { b = idx[s.charCodeAt(i++)]; r |= (b & 31) << sh; sh += 5; } while (b >= 32);\n");
    js.Append("      lon += (r & 1) ? ~(r >> 1) : (r >> 1);\n");
    js.Append("      r = 0; sh = 0;\n");
    js.Append("      do { b = idx[s.charCodeAt(i++)]; r |= (b & 31) << sh; sh += 5; } while (b >= 32);\n");
    js.Append("      lat += (r & 1) ? ~(r >> 1) : (r >> 1);\n");
    js.Append("      ring.push([lon / 100, lat / 100]);\n");
    js.Append("    }\n");
    js.Append("    return { iso, ring };\n");
    js.Append("  });\n}\n\n");
    js.Append("const LAND = decodeShapes('").Append(sbF).Append("');\n\n");
    js.Append("const LAND_LOW = decodeShapes('").Append(sbC).Append("');\n");
    File.WriteAllText(outPath, js.ToString(), new UTF8Encoding(false));

    return string.Format(CultureInfo.InvariantCulture,
      "rings {0} fine / {1} coarse   points {2} / {3}   chars {4} / {5}",
      nF, nC, ptF, ptC, sbF.Length, sbC.Length);
  }
}
'@

$sw = [Diagnostics.Stopwatch]::StartNew()
$stats = [ShapeBuild]::Run($src, $out, $TolFine, $TolCoarse, $MinFine, $MinCoarse)
"{0}" -f $stats
"{0}  {1:N1} KB  ({2:N1}s)" -f $out, ((Get-Item $out).Length / 1KB), $sw.Elapsed.TotalSeconds
