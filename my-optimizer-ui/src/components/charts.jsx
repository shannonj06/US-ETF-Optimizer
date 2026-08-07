// Lightweight, dependency-free SVG charts for the Cash Analysis page.
//
// Palette + formatting helpers live in ./chartUtils.js (this file exports only
// components, per React Fast Refresh). Positive/negative money is never encoded
// by color alone: tooltips, tables and axis labels always carry +/- signs and
// formatted values.

import { useRef, useState } from "react";
import { fmtCompact, fmtCurrency } from "./chartUtils.js";

// Chart chrome resolves from CSS variables (via classes styled in App.css), so
// grid / axis / label tones follow the active theme. Series colors stay explicit
// (they carry identity and read on both light and dark surfaces).

// "nice" axis ticks spanning [min, max].
function niceTicks(min, max, count = 5) {
  if (min === max) {
    const pad = Math.abs(min) || 1;
    min -= pad;
    max += pad;
  }
  const range = max - min;
  const rawStep = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  const step = (norm >= 5 ? 5 : norm >= 2 ? 2 : 1) * mag;
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = niceMin; v <= niceMax + step / 2; v += step) {
    ticks.push(Number(v.toFixed(10)));
  }
  return { ticks, niceMin, niceMax };
}

// Container that reports the hovered fractional-x so an HTML tooltip can be
// absolutely positioned over the SVG (SVG coords scale with the viewBox).
function ChartFrame({ children, tooltip, width, height, ariaLabel }) {
  const ref = useRef(null);
  return (
    <div className="ca-chart-frame" ref={ref} role="img" aria-label={ariaLabel}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="ca-chart-svg"
      >
        {children}
      </svg>
      {tooltip}
    </div>
  );
}

// ── Line chart (multi-series, selectable lines, crosshair tooltip) ───────────
export function LineChart({
  xLabels,
  series, // [{ key, label, color, values, dashed }]
  height = 340,
  valueFormat = fmtCompact,
  tooltipValueFormat = fmtCurrency,
  ariaLabel = "Line chart",
}) {
  const W = 860;
  const H = height;
  const padL = 70;
  const padR = 24;
  const padT = 18;
  const padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const [hover, setHover] = useState(null);

  const visible = series.filter((s) => s.values && s.values.length);
  const n = xLabels.length;

  let min = Infinity;
  let max = -Infinity;
  for (const s of visible) {
    for (const v of s.values) {
      if (v == null || Number.isNaN(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  if (!Number.isFinite(min)) {
    min = 0;
    max = 1;
  }
  const { ticks, niceMin, niceMax } = niceTicks(min, max, 5);

  const xAt = (i) => (n <= 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW);
  const yAt = (v) => padT + (1 - (v - niceMin) / (niceMax - niceMin)) * plotH;

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const frac = (px - padL) / plotW;
    let i = Math.round(frac * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    setHover(i);
  };

  // X-axis labels: ~7 evenly spaced.
  const labelStep = Math.max(1, Math.ceil(n / 7));

  const tooltip =
    hover != null ? (
      <div
        className="ca-tooltip"
        style={{
          left: `${(xAt(hover) / W) * 100}%`,
          transform:
            xAt(hover) > W * 0.6 ? "translate(-105%, 0)" : "translate(8px, 0)",
        }}
      >
        <div className="ca-tooltip-title">{xLabels[hover]}</div>
        {visible.map((s) => (
          <div key={s.key} className="ca-tooltip-row">
            <span className="ca-swatch" style={{ background: s.color }} />
            <span className="ca-tooltip-label">{s.label}</span>
            <span className="ca-tooltip-val">
              {tooltipValueFormat(s.values[hover])}
            </span>
          </div>
        ))}
      </div>
    ) : null;

  return (
    <ChartFrame width={W} height={H} tooltip={tooltip} ariaLabel={ariaLabel}>
      {/* gridlines + y labels */}
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={padL}
            x2={W - padR}
            y1={yAt(t)}
            y2={yAt(t)}
            className="ca-grid"
            strokeWidth="1"
          />
          <text
            x={padL - 8}
            y={yAt(t) + 4}
            textAnchor="end"
            fontSize="11"
            className="ca-axis-label"
          >
            {valueFormat(t)}
          </text>
        </g>
      ))}
      {/* x labels */}
      {xLabels.map((lbl, i) =>
        i % labelStep === 0 || i === n - 1 ? (
          <text
            key={i}
            x={xAt(i)}
            y={H - padB + 20}
            textAnchor="middle"
            fontSize="11"
            className="ca-axis-label"
          >
            {lbl}
          </text>
        ) : null
      )}
      {/* baseline */}
      <line
        x1={padL}
        x2={W - padR}
        y1={padT + plotH}
        y2={padT + plotH}
        className="ca-axis"
        strokeWidth="1"
      />
      {/* subtle area fills under solid lines (gradient to transparent) */}
      <defs>
        {visible.map((s) =>
          s.dashed ? null : (
            <linearGradient key={s.key} id={`area-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.18" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0" />
            </linearGradient>
          )
        )}
      </defs>
      {visible.map((s) => {
        if (s.dashed) return null;
        const pts = s.values
          .map((v, i) => (v == null || Number.isNaN(v) ? null : [xAt(i), yAt(v)]))
          .filter(Boolean);
        if (pts.length < 2) return null;
        const base = padT + plotH;
        const area =
          `M${pts[0][0]},${base} ` +
          pts.map(([x, y]) => `L${x},${y}`).join(" ") +
          ` L${pts[pts.length - 1][0]},${base} Z`;
        return <path key={`fill-${s.key}`} d={area} fill={`url(#area-${s.key})`} stroke="none" />;
      })}
      {/* series lines */}
      {visible.map((s) => {
        const d = s.values
          .map((v, i) =>
            v == null || Number.isNaN(v)
              ? null
              : `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(v)}`
          )
          .filter(Boolean)
          .join(" ");
        return (
          <path
            key={s.key}
            d={d}
            fill="none"
            stroke={s.color}
            strokeWidth="2"
            strokeDasharray={s.dashed ? "6 5" : undefined}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        );
      })}
      {/* crosshair + dots */}
      {hover != null && (
        <>
          <line
            x1={xAt(hover)}
            x2={xAt(hover)}
            y1={padT}
            y2={padT + plotH}
            className="ca-axis"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
          {visible.map((s) =>
            s.values[hover] == null ? null : (
              <circle
                key={s.key}
                cx={xAt(hover)}
                cy={yAt(s.values[hover])}
                r="4"
                fill="#fff"
                stroke={s.color}
                strokeWidth="2"
              />
            )
          )}
        </>
      )}
      {/* hover capture */}
      <rect
        x={padL}
        y={padT}
        width={plotW}
        height={plotH}
        fill="transparent"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      />
    </ChartFrame>
  );
}

// ── Bar chart (stacked or grouped, supports negatives) ───────────────────────
export function BarChart({
  categories, // string[]
  series, // [{ key, label, color, values }]
  mode = "stacked", // "stacked" | "grouped"
  height = 340,
  valueFormat = fmtCompact,
  tooltipValueFormat = fmtCurrency,
  extraLine, // optional { label, color, values } drawn as an overlay line (e.g. cumulative)
  ariaLabel = "Bar chart",
}) {
  const W = 860;
  const H = height;
  const padL = 70;
  const padR = 24;
  const padT = 18;
  const padB = 52;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const [hover, setHover] = useState(null);

  const n = categories.length;
  const visible = series.filter((s) => s.values && s.values.length);

  // y-range: stacked sums (pos/neg separately) or raw values for grouped.
  let min = 0;
  let max = 0;
  for (let i = 0; i < n; i++) {
    if (mode === "stacked") {
      let pos = 0;
      let neg = 0;
      for (const s of visible) {
        const v = s.values[i] || 0;
        if (v >= 0) pos += v;
        else neg += v;
      }
      max = Math.max(max, pos);
      min = Math.min(min, neg);
    } else {
      for (const s of visible) {
        const v = s.values[i] || 0;
        max = Math.max(max, v);
        min = Math.min(min, v);
      }
    }
  }
  if (extraLine) {
    for (const v of extraLine.values) {
      if (v == null) continue;
      max = Math.max(max, v);
      min = Math.min(min, v);
    }
  }
  const { ticks, niceMin, niceMax } = niceTicks(min, max, 5);
  const yAt = (v) => padT + (1 - (v - niceMin) / (niceMax - niceMin)) * plotH;
  const zeroY = yAt(0);

  const band = plotW / Math.max(1, n);
  const barInset = Math.min(14, band * 0.18);
  const groupW = band - barInset * 2;
  const barW = mode === "grouped" ? groupW / Math.max(1, visible.length) : groupW;

  const labelStep = Math.max(1, Math.ceil(n / 12));

  const catCenter = (i) => padL + band * i + band / 2;

  const tooltip =
    hover != null ? (
      <div
        className="ca-tooltip"
        style={{
          left: `${(catCenter(hover) / W) * 100}%`,
          transform:
            catCenter(hover) > W * 0.6
              ? "translate(-105%, 0)"
              : "translate(8px, 0)",
        }}
      >
        <div className="ca-tooltip-title">{categories[hover]}</div>
        {visible.map((s) => (
          <div key={s.key} className="ca-tooltip-row">
            <span className="ca-swatch" style={{ background: s.color }} />
            <span className="ca-tooltip-label">{s.label}</span>
            <span className="ca-tooltip-val">
              {tooltipValueFormat(s.values[hover] || 0)}
            </span>
          </div>
        ))}
        {extraLine && (
          <div className="ca-tooltip-row">
            <span
              className="ca-swatch"
              style={{ background: extraLine.color }}
            />
            <span className="ca-tooltip-label">{extraLine.label}</span>
            <span className="ca-tooltip-val">
              {tooltipValueFormat(extraLine.values[hover] || 0)}
            </span>
          </div>
        )}
      </div>
    ) : null;

  return (
    <ChartFrame width={W} height={H} tooltip={tooltip} ariaLabel={ariaLabel}>
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={padL}
            x2={W - padR}
            y1={yAt(t)}
            y2={yAt(t)}
            className="ca-grid"
            strokeWidth="1"
          />
          <text
            x={padL - 8}
            y={yAt(t) + 4}
            textAnchor="end"
            fontSize="11"
            className="ca-axis-label"
          >
            {valueFormat(t)}
          </text>
        </g>
      ))}
      {/* zero baseline (emphasized) */}
      <line
        x1={padL}
        x2={W - padR}
        y1={zeroY}
        y2={zeroY}
        className="ca-axis"
        strokeWidth="1.5"
      />
      {/* bars */}
      {categories.map((cat, i) => {
        if (mode === "stacked") {
          let posTop = 0;
          let negBot = 0;
          return (
            <g key={i}>
              {visible.map((s) => {
                const v = s.values[i] || 0;
                if (v === 0) return null;
                let y;
                let h;
                if (v >= 0) {
                  const yTop = yAt(posTop + v);
                  const yBase = yAt(posTop);
                  y = yTop;
                  h = yBase - yTop;
                  posTop += v;
                } else {
                  const yTop = yAt(negBot);
                  const yBase = yAt(negBot + v);
                  y = yTop;
                  h = yBase - yTop;
                  negBot += v;
                }
                return (
                  <rect
                    key={s.key}
                    x={padL + band * i + barInset}
                    y={y}
                    width={barW}
                    height={Math.max(0, h - 2)}
                    rx="3"
                    fill={s.color}
                    opacity={hover == null || hover === i ? 1 : 0.55}
                  />
                );
              })}
            </g>
          );
        }
        // grouped
        return (
          <g key={i}>
            {visible.map((s, si) => {
              const v = s.values[i] || 0;
              const yTop = v >= 0 ? yAt(v) : zeroY;
              const h = Math.abs(yAt(v) - zeroY);
              return (
                <rect
                  key={s.key}
                  x={padL + band * i + barInset + si * barW}
                  y={yTop}
                  width={Math.max(1, barW - 2)}
                  height={Math.max(0, h)}
                  rx="2"
                  fill={s.color}
                  opacity={hover == null || hover === i ? 1 : 0.55}
                />
              );
            })}
          </g>
        );
      })}
      {/* optional cumulative overlay line */}
      {extraLine && (
        <path
          d={extraLine.values
            .map((v, i) =>
              v == null ? null : `${i === 0 ? "M" : "L"}${catCenter(i)},${yAt(v)}`
            )
            .filter(Boolean)
            .join(" ")}
          fill="none"
          stroke={extraLine.color}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
      )}
      {/* x labels */}
      {categories.map((cat, i) =>
        i % labelStep === 0 || i === n - 1 ? (
          <text
            key={i}
            x={catCenter(i)}
            y={H - padB + 18}
            textAnchor="middle"
            fontSize="10"
            className="ca-axis-label"
          >
            {cat}
          </text>
        ) : null
      )}
      {/* hover capture bands */}
      {categories.map((cat, i) => (
        <rect
          key={i}
          x={padL + band * i}
          y={padT}
          width={band}
          height={plotH}
          fill="transparent"
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
        />
      ))}
    </ChartFrame>
  );
}

// Legend with toggle support. items: [{ key, label, color, visible }].
export function ChartLegend({ items, onToggle }) {
  return (
    <div className="ca-legend">
      {items.map((it) => (
        <button
          type="button"
          key={it.key}
          className={`ca-legend-item${it.visible === false ? " off" : ""}`}
          onClick={onToggle ? () => onToggle(it.key) : undefined}
          disabled={!onToggle}
        >
          <span className="ca-swatch" style={{ background: it.color }} />
          {it.label}
        </button>
      ))}
    </div>
  );
}
