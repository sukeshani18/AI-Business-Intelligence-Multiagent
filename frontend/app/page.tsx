"use client";

import { FormEvent, useMemo, useState } from "react";
import { jsPDF } from "jspdf";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Row = Record<string, string>;
type KPI = { label: string; value: number; format?: "currency" | "number" };
type Point = { name: string; value: number };
type TrendPoint = { period: string; value: number };
type FixedChart = { column: string | null; data: Point[] };
type DashboardData = {
  filename: string;
  totalRecords: number;
  totalColumns: number;
  columns: string[];
  numericColumns: string[];
  categoricalColumns: string[];
  dateColumn: string | null;
  metricColumn: string | null;
  nameChart: FixedChart;
  productChart: FixedChart;
  categoryChart: FixedChart;
  kpis: KPI[];
  trendData: TrendPoint[];
  preview: Row[];
};

function parseCSV(text: string): Row[] {
  const input = text.replace(/^\uFEFF/, "");
  const records: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];
    if (char === '"') {
      if (quoted && input[i + 1] === '"') {
        cell += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && input[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some((value) => value.trim() !== "")) records.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  row.push(cell);
  if (row.some((value) => value.trim() !== "")) records.push(row);
  if (records.length < 2) throw new Error("The CSV file has no data rows.");

  const headers = records[0].map((header, index) => header.trim() || `Column ${index + 1}`);
  return records.slice(1).map((values) => {
    const result: Row = {};
    headers.forEach((header, index) => {
      result[header] = (values[index] ?? "").trim();
    });
    return result;
  });
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const negative = /^\(.*\)$/.test(raw);
  const cleaned = raw.replace(/[₹$€£,%()\s]/g, "").replace(/,/g, "");
  if (!cleaned || !/^-?\d+(\.\d+)?$/.test(cleaned)) return null;
  const parsed = Number(cleaned) * (negative ? -1 : 1);
  return Number.isFinite(parsed) ? parsed : null;
}

function niceName(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

function parseDateValue(value: string): Date | null {
  const raw = value.trim();
  if (!raw) return null;
  let match = raw.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (match) {
    const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return Number.isNaN(date.getTime()) ? null : date;
  }
  match = raw.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/);
  if (match) {
    const first = Number(match[1]);
    const second = Number(match[2]);
    const year = Number(match[3]);
    const day = first > 12 ? first : second > 12 ? second : first;
    const month = first > 12 ? second : second > 12 ? first : second;
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function buildDashboard(rows: Row[], filename: string): DashboardData {
  if (!rows.length) throw new Error("The uploaded CSV contains no records.");
  const columns = Object.keys(rows[0] ?? {});
  const normalized = (column: string) => column.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const findColumn = (patterns: RegExp[]) => columns.find((column) => patterns.some((pattern) => pattern.test(normalized(column)))) ?? null;
  const dateColumn = findColumn([/(^|_)(order_)?date($|_)/, /timestamp/, /(^|_)time($|_)/]) ?? columns.find((column) => {
    const values = rows.map((row) => row[column]).filter(Boolean).slice(0, 50);
    return values.length >= 2 && values.filter((value) => parseDateValue(value) !== null).length / values.length >= 0.7;
  }) ?? null;
  const numericColumns = columns.filter((column) => {
    if (column === dateColumn) return false;
    const values = rows.map((row) => row[column]).filter((value) => value.trim() !== "");
    return values.length > 0 && values.filter((value) => toNumber(value) !== null).length / values.length >= 0.7;
  });
  const metricColumn = findColumn([/(^|_)(sales|revenue|profit|amount|total_sales|total_revenue|net_sales|order_value|price|value|cost|quantity|qty)($|_)/])
    ?? numericColumns.find((column) => /(sales|revenue|profit|amount|price|value|cost|quantity|qty)/i.test(column))
    ?? numericColumns[0]
    ?? null;
  const valuesFor = (column: string) => rows.map((row) => toNumber(row[column])).filter((value): value is number => value !== null);
  const aggregate = (column: string | null, mode: "sum" | "count" = "sum"): Point[] => {
    if (!column) return [];
    const totals = new Map<string, number>();
    rows.forEach((row) => {
      const label = row[column]?.trim() || "Unknown";
      const value = mode === "count" ? 1 : (metricColumn ? toNumber(row[metricColumn]) ?? 0 : 1);
      totals.set(label, (totals.get(label) ?? 0) + value);
    });
    return [...totals].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 8);
  };
  // These are intentionally fixed to the requested Power BI-style visual roles.
  // We do not generate a chart for every categorical column in the CSV.
  const nameColumn = findColumn([/^name$/, /^customer_name$/, /^client_name$/, /^employee_name$/, /^salesperson$/, /^representative$/, /^account_name$/]);
  const productColumn = findColumn([/(^|_)(product|product_name|item|item_name|sku)($|_)/]);
  const categoryColumn = findColumn([/(^|_)(category|product_category|sub_category|subcategory|class)($|_)/]);
  const nameChart: FixedChart = { column: nameColumn, data: aggregate(nameColumn) };
  const productChart: FixedChart = { column: productColumn, data: aggregate(productColumn) };
  const categoryChart: FixedChart = { column: categoryColumn, data: aggregate(categoryColumn) };

  const kpis: KPI[] = [{ label: "Total Records", value: rows.length, format: "number" }];
  const salesColumn = findColumn([/(^|_)(sales|revenue|amount|total_sales|total_revenue|net_sales)($|_)/]);
  const profitColumn = findColumn([/(^|_)(profit|net_profit|gross_profit|earnings)($|_)/]);
  const orderIdColumn = findColumn([/(^|_)(order_id|invoice_id|transaction_id)($|_)/]);
  const customerIdColumn = findColumn([/(^|_)(customer_id|client_id)($|_)/]);
  if (salesColumn) kpis.push({ label: "Total Sales", value: valuesFor(salesColumn).reduce((a, b) => a + b, 0), format: "currency" });
  if (profitColumn && kpis.length < 4) kpis.push({ label: "Total Profit", value: valuesFor(profitColumn).reduce((a, b) => a + b, 0), format: "currency" });
  if (orderIdColumn && kpis.length < 4) kpis.push({ label: "Unique Orders", value: new Set(rows.map((row) => row[orderIdColumn]).filter(Boolean)).size, format: "number" });
  if (customerIdColumn && kpis.length < 4) kpis.push({ label: "Unique Customers", value: new Set(rows.map((row) => row[customerIdColumn]).filter(Boolean)).size, format: "number" });
  if (kpis.length < 4 && metricColumn && !kpis.some((kpi) => kpi.label === `Total ${niceName(metricColumn)}`)) {
    kpis.push({ label: `Total ${niceName(metricColumn)}`, value: valuesFor(metricColumn).reduce((a, b) => a + b, 0), format: /(sales|revenue|profit|amount|price|cost)/i.test(metricColumn) ? "currency" : "number" });
  }

  const trendGroups = new Map<string, number>();
  if (dateColumn && metricColumn) {
    rows.forEach((row) => {
      const date = parseDateValue(row[dateColumn]);
      const value = toNumber(row[metricColumn]);
      if (!date || value === null) return;
      const period = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
      trendGroups.set(period, (trendGroups.get(period) ?? 0) + value);
    });
  }
  const trendData = [...trendGroups].sort(([a], [b]) => a.localeCompare(b)).map(([period, value]) => ({ period, value }));
  return {
    filename, totalRecords: rows.length, totalColumns: columns.length, columns,
    numericColumns, categoricalColumns: columns.filter((column) => !numericColumns.includes(column) && column !== dateColumn),
    dateColumn, metricColumn, nameChart, productChart, categoryChart, kpis: kpis.slice(0, 4),
    trendData, preview: rows.slice(0, 10),
  };
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h2 className="text-lg font-semibold tracking-tight text-white">{title}</h2>
      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
    </div>
  );
}

function BarChart({ data, currency = false }: { data: Point[]; currency?: boolean }) {
  if (!data.length) return <EmptyChart message="No suitable category or numerical values were found in this CSV." />;
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="space-y-4">
      {data.map((item, index) => (
        <div key={`${item.name}-${index}`}>
          <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
            <span className="max-w-[62%] truncate text-slate-300" title={item.name}>{item.name}</span>
            <span className="shrink-0 font-medium tabular-nums text-slate-200">{currency ? formatCurrency(item.value) : formatNumber(item.value)}</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${Math.max(1, (item.value / max) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function TrendChart({ data }: { data: TrendPoint[] }) {
  if (!data.length) return <EmptyChart message="A date column and a numerical metric are needed for a time trend." />;
  const width = 640;
  const height = 230;
  const pad = 34;
  const max = Math.max(...data.map((item) => item.value), 1);
  const points = data.map((item, index) => {
    const x = pad + (data.length === 1 ? (width - pad * 2) / 2 : (index / (data.length - 1)) * (width - pad * 2));
    const y = height - pad - (item.value / max) * (height - pad * 2);
    return `${x},${y}`;
  }).join(" ");
  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[230px] w-full" role="img" aria-label="Date-wise performance line chart">
        {[0, 1, 2, 3].map((line) => <line key={line} x1={pad} x2={width - pad} y1={pad + line * ((height - pad * 2) / 3)} y2={pad + line * ((height - pad * 2) / 3)} stroke="#263244" strokeDasharray="4 5" />)}
        <polyline points={points} fill="none" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((item, index) => {
          const x = pad + (data.length === 1 ? (width - pad * 2) / 2 : (index / (data.length - 1)) * (width - pad * 2));
          const y = height - pad - (item.value / max) * (height - pad * 2);
          const labelStep = Math.max(1, Math.ceil(data.length / 7));
          return <g key={item.period}><circle cx={x} cy={y} r="4.5" fill="#22d3ee" stroke="#0f172a" strokeWidth="2" />{(index % labelStep === 0 || index === data.length - 1) && <text x={x} y={height - 8} fill="#94a3b8" fontSize="9" textAnchor="middle">{item.period}</text>}</g>;
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400"><span>Date-wise performance</span><span>{data.length} dates</span></div>
    </div>
  );
}

function DistributionChart({ data }: { data: Point[] }) {
  if (!data.length) return <EmptyChart message="No category distribution is available for this dataset." />;
  const total = data.reduce((sum, item) => sum + item.value, 0) || 1;
  const palette = ["#22d3ee", "#818cf8", "#34d399", "#fbbf24", "#f472b6", "#a78bfa"];
  let offset = 0;
  const stops = data.map((item, index) => {
    const start = offset;
    offset += (item.value / total) * 100;
    return `${palette[index % palette.length]} ${start}% ${offset}%`;
  }).join(", ");
  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-center">
      <div className="relative h-44 w-44 shrink-0 rounded-full" style={{ background: `conic-gradient(${stops})` }}>
        <div className="absolute inset-7 flex flex-col items-center justify-center rounded-full bg-[#111827]"><span className="text-2xl font-bold text-white">{formatNumber(total)}</span><span className="text-[10px] uppercase tracking-wider text-slate-500">Total</span></div>
      </div>
      <div className="w-full space-y-2">
        {data.map((item, index) => <div key={`${item.name}-${index}`} className="flex items-center justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2 text-slate-300"><span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: palette[index % palette.length] }} /><span className="truncate">{item.name}</span></span><span className="shrink-0 tabular-nums text-slate-400">{((item.value / total) * 100).toFixed(1)}%</span></div>)}
      </div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return <div className="flex min-h-[210px] items-center justify-center rounded-xl border border-dashed border-slate-700 px-6 text-center text-xs leading-6 text-slate-500">{message}</div>;
}

export default function Home() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [question, setQuestion] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [insights, setInsights] = useState("");
  const [loading, setLoading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [reportError, setReportError] = useState("");
  const [fileName, setFileName] = useState("");

  const computed = useMemo(() => dashboard, [dashboard]);

  async function handleUpload(file: File) {
    setLoading(true);
    setError("");
    setDashboard(null);
    setRows([]);
    setAnalysis("");
    setInsights("");
    setFileName(file.name);
    try {
      const csvText = await file.text();
      const parsedRows = parseCSV(csvText);
      const localDashboard = buildDashboard(parsedRows, file.name);

      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
      const responseData = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(responseData.detail || "The backend could not process this CSV.");

      setRows(parsedRows);
      setDashboard(localDashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this CSV file.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setError("");
    setAnalysis("");
    setInsights("");
    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "The AI agents could not answer this question.");
      setAnalysis(data.analysis || "No analyst response was returned.");
      setInsights(data.insights || "No business insights were returned.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI analysis failed.");
    } finally {
      setAsking(false);
    }
  }

  function downloadReport() {
    if (!computed) return;
    setDownloading(true);
    setReportError("");
    try {
      const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const margin = 13;
      const contentW = pageW - margin * 2;
      const dark = [8, 13, 24] as const;
      const panel = [18, 29, 45] as const;
      const cyan = [34, 211, 238] as const;
      const white = [241, 245, 249] as const;
      const muted = [148, 163, 184] as const;
      const palette = [[34,211,238],[129,140,248],[52,211,153],[251,191,36],[244,114,182],[167,139,250]] as const;
      const bg = () => { pdf.setFillColor(...dark); pdf.rect(0, 0, pageW, pageH, "F"); };
      const header = (title: string, subtitle: string) => {
        bg(); pdf.setFont("helvetica", "bold"); pdf.setFontSize(8); pdf.setTextColor(...cyan); pdf.text("AI-POWERED BUSINESS INTELLIGENCE", margin, 12);
        pdf.setFontSize(19); pdf.setTextColor(...white); pdf.text(title, margin, 22);
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.setTextColor(...muted); pdf.text(subtitle, margin, 29);
        pdf.setDrawColor(45, 58, 77); pdf.line(margin, 34, pageW - margin, 34);
      };
      const panelBox = (x: number, y: number, w: number, h: number) => { pdf.setFillColor(...panel); pdf.roundedRect(x, y, w, h, 2, 2, "F"); };
      const section = (label: string, y: number) => { pdf.setFont("helvetica", "bold"); pdf.setFontSize(11); pdf.setTextColor(...white); pdf.text(label, margin, y); };
      const drawBar = (data: Point[], x: number, y: number, w: number, h: number) => {
        const visible = data.slice(0, 7); const max = Math.max(1, ...visible.map((d) => d.value));
        visible.forEach((item, i) => {
          const yy = y + 8 + i * ((h - 14) / Math.max(1, visible.length));
          pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(...muted); pdf.text(item.name.slice(0, 23), x + 4, yy + 3);
          const bx = x + w * 0.43, bw = w * 0.40;
          pdf.setFillColor(38, 50, 68); pdf.roundedRect(bx, yy, bw, 3.5, 1, 1, "F");
          pdf.setFillColor(...cyan); pdf.roundedRect(bx, yy, Math.max(0.8, bw * item.value / max), 3.5, 1, 1, "F");
          pdf.setTextColor(...white); pdf.text(formatNumber(item.value), x + w - 4, yy + 3, { align: "right" });
        });
      };
      const drawPie = (data: Point[], x: number, y: number, w: number, h: number) => {
        const visible = data.slice(0, 8); const total = visible.reduce((sum, d) => sum + d.value, 0) || 1;
        const cx = x + 29, cy = y + h / 2, radius = Math.min(20, h * 0.32);
        let angle = -Math.PI / 2;
        visible.forEach((item, index) => {
          const portion = Math.max(1, Math.round(item.value / total * 48));
          const end = angle + (item.value / total) * Math.PI * 2;
          for (let step = 0; step < portion; step++) {
            const a1 = angle + (end - angle) * step / portion;
            const a2 = angle + (end - angle) * (step + 1) / portion;
            pdf.setFillColor(...palette[index % palette.length]);
            pdf.triangle(cx, cy, cx + radius * Math.cos(a1), cy + radius * Math.sin(a1), cx + radius * Math.cos(a2), cy + radius * Math.sin(a2), "F");
          }
          angle = end;
          const ly = y + 8 + index * 8;
          pdf.setFillColor(...palette[index % palette.length]); pdf.circle(x + 61, ly - 1, 1.3, "F");
          pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(...muted); pdf.text(item.name.slice(0, 12), x + 65, ly);
          pdf.setTextColor(...white); pdf.text(`${(item.value / total * 100).toFixed(1)}%`, x + w - 4, ly, { align: "right" });
        });
      };
      const drawTrend = (x: number, y: number, w: number, h: number) => {
        const data = computed.trendData;
        if (!data.length) { pdf.setFontSize(9); pdf.setTextColor(...muted); pdf.text("No usable date and numeric metric combination was detected.", x + 8, y + h / 2); return; }
        const left = x + 10, right = x + w - 10, top = y + 10, bottom = y + h - 14;
        [0,1,2,3].forEach((i) => { const gy = top + i * (bottom - top) / 3; pdf.setDrawColor(45,58,77); pdf.line(left, gy, right, gy); });
        const max = Math.max(1, ...data.map((point) => point.value));
        const coords = data.map((point, i) => ({ x: left + (data.length === 1 ? (right-left)/2 : i/(data.length-1)*(right-left)), y: bottom - point.value/max*(bottom-top) }));
        pdf.setDrawColor(...cyan); pdf.setLineWidth(1.1);
        for (let i=1;i<coords.length;i++) pdf.line(coords[i-1].x,coords[i-1].y,coords[i].x,coords[i].y);
        coords.forEach((point,i) => { pdf.setFillColor(...cyan); pdf.circle(point.x,point.y,1.1,"F"); if (i % Math.max(1,Math.ceil(coords.length/14))===0 || i===coords.length-1) { pdf.setFontSize(6); pdf.setTextColor(...muted); pdf.text(data[i].period,point.x,bottom+8,{align:"center"}); } });
      };
      const footer = (page: number) => { pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(...muted); pdf.text(`Generated from ${computed.filename}  |  Page ${page}`, margin, pageH - 6); };

      header("Business Performance Report", `${computed.filename}  |  ${computed.totalRecords.toLocaleString("en-IN")} records  |  ${computed.totalColumns} fields`);
      section("Key performance indicators", 44);
      const kGap = 5, kW = (contentW - kGap * 3) / 4;
      computed.kpis.forEach((kpi, i) => {
        const x = margin + i * (kW + kGap); panelBox(x, 49, kW, 25);
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.setTextColor(...muted); pdf.text(kpi.label, x + 4, 58);
        pdf.setFont("helvetica", "bold"); pdf.setFontSize(15); pdf.setTextColor(...cyan); pdf.text(kpi.format === "currency" ? `INR ${formatNumber(kpi.value)}` : formatNumber(kpi.value), x + 4, 68, { maxWidth: kW - 8 });
      });
      section("Business performance by key dimensions", 87);
      const boxGap = 5, boxW = (contentW - boxGap * 2) / 3;
      const fixedCharts = [
        { title: "Name performance", chart: computed.nameChart, kind: "bar" as const },
        { title: "Product mix", chart: computed.productChart, kind: "pie" as const },
        { title: "Category performance", chart: computed.categoryChart, kind: "bar" as const },
      ];
      fixedCharts.forEach((item, i) => {
        const x = margin + i * (boxW + boxGap); panelBox(x, 92, boxW, 101);
        pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.setTextColor(...white); pdf.text(item.title, x + 4, 100);
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(6.5); pdf.setTextColor(...muted);
        pdf.text(item.chart.column ? `By ${niceName(item.chart.column)}` : "Matching CSV field not found", x + 4, 106);
        if (!item.chart.data.length) {
          pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(...muted);
          pdf.text("Required field not found in this dataset.", x + 5, 145, { maxWidth: boxW - 10 });
        } else if (item.kind === "pie") drawPie(item.chart.data, x + 2, 110, boxW - 4, 78);
        else drawBar(item.chart.data, x + 2, 110, boxW - 4, 78);
      });
      footer(1);

      pdf.addPage();
      header("Date-wise business performance", `${computed.metricColumn ? niceName(computed.metricColumn) : "Business metric"} across available dates`);
      section("Daily trend", 45); panelBox(margin, 51, contentW, 125); drawTrend(margin + 3, 54, contentW - 6, 118);
      footer(2);

      pdf.addPage();
      header("Dataset preview", `First ${computed.preview.length} rows of ${computed.totalRecords.toLocaleString("en-IN")} total records`);
      const cols = computed.columns.slice(0, 8), tableY = 45, colW = contentW / Math.max(1, cols.length);
      cols.forEach((column, i) => { const x = margin + i * colW; pdf.setFillColor(27,42,61); pdf.rect(x,tableY,colW,10,"F"); pdf.setFont("helvetica","bold"); pdf.setFontSize(6.5); pdf.setTextColor(...cyan); pdf.text(niceName(column).slice(0,20),x+2,tableY+6); });
      computed.preview.forEach((row, ri) => cols.forEach((column, ci) => { const x=margin+ci*colW, y=tableY+10+ri*9; pdf.setFillColor(ri%2?14:18,ri%2?23:28,ri%2?37:44); pdf.rect(x,y,colW,9,"F"); pdf.setFont("helvetica","normal"); pdf.setFontSize(6.2); pdf.setTextColor(...white); pdf.text(String(row[column]??"").slice(0,24),x+2,y+5.8,{maxWidth:colW-4}); }));
      if (computed.columns.length > 8) { pdf.setFontSize(8); pdf.setTextColor(...muted); pdf.text(`Showing first 8 of ${computed.columns.length} columns.`, margin, tableY + 10 + computed.preview.length * 9 + 8); }
      footer(3);
      pdf.save("Business_Intelligence_Report.pdf");
    } catch (err) {
      console.error("PDF generation error", err);
      setReportError(err instanceof Error ? err.message : "Could not create the PDF report.");
    } finally { setDownloading(false); }
  }

  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <div className="mx-auto max-w-[1500px] px-5 py-8 md:px-9">
        <header className="mb-8 flex flex-col justify-between gap-5 border-b border-slate-800 pb-7 md:flex-row md:items-center">
          <div>
            <p className="mb-2 text-[11px] font-semibold tracking-[0.22em] text-cyan-400">AI-POWERED ANALYTICS PLATFORM</p>
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Business Intelligence</h1>
            <p className="mt-2 text-sm text-slate-400">Multi-agent data analysis, performance monitoring and business insights</p>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-[#111b2b] px-4 py-3">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_#34d399]" />
            <div><p className="text-[10px] font-semibold tracking-wider text-slate-500">PLATFORM STATUS</p><p className="mt-0.5 text-sm font-medium text-emerald-300">Ready for analysis</p></div>
          </div>
        </header>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6">
          <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
            <div><h2 className="font-semibold text-white">Upload business dataset</h2><p className="mt-1 text-xs text-slate-400">Select a CSV file to build your dashboard automatically.</p></div>
            {fileName && <span className="max-w-full truncate rounded-lg border border-slate-700 bg-[#0b1422] px-3 py-2 text-xs text-cyan-300">{fileName}</span>}
          </div>
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-slate-600 bg-[#0b1422] px-5 py-8 text-center transition hover:border-cyan-500 hover:bg-[#0d1929]">
            <span className="mb-2 text-2xl">⇧</span><span className="text-sm font-semibold text-slate-200">Choose CSV file</span><span className="mt-1 text-xs text-slate-500">CSV format · Full dataset analysis</span>
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleUpload(file); event.target.value = ""; }} />
          </label>
          {loading && <p className="mt-4 text-sm text-cyan-300">Uploading and analysing your dataset…</p>}
          {error && <p className="mt-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">{error}</p>}
        </section>

        {!computed && !loading && <section className="rounded-2xl border border-slate-800 bg-[#111b2b] px-6 py-16 text-center"><div className="mb-4 text-4xl">▤</div><h2 className="text-lg font-semibold">Your analytics workspace is ready</h2><p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">Upload a CSV file to generate business KPIs, product and regional visual analytics, and an exportable report.</p></section>}

        {computed && (
          <>
            <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div><h2 className="text-lg font-semibold">Business performance overview</h2><p className="mt-1 text-xs text-slate-400">{computed.filename} · {computed.totalRecords.toLocaleString("en-IN")} records analysed</p></div>
              <button type="button" onClick={downloadReport} disabled={downloading} className="rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-950/30 transition hover:bg-cyan-500 disabled:opacity-60">{downloading ? "Generating report…" : "↓ Download PDF report"}</button>
            </div>
            {reportError && <p className="mb-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">PDF error: {reportError}</p>}

            <section className="mb-8">
              <SectionTitle title="Key performance indicators" />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {computed.kpis.map((kpi, index) => <div key={`${kpi.label}-${index}`} className="rounded-xl border border-slate-800 bg-[#111b2b] p-5"><p className="text-xs font-medium text-slate-400">{kpi.label}</p><p className="mt-3 break-words text-2xl font-bold tracking-tight text-white">{kpi.format === "currency" ? formatCurrency(kpi.value) : formatNumber(kpi.value)}</p></div>)}
              </div>
            </section>

            <section className="mb-8">
              <SectionTitle title="Business data visualizations" subtitle="Each visual has a defined business purpose: Name performance, Product mix, Category performance and date-wise trend." />
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6">
                  <div className="mb-5"><h3 className="text-sm font-semibold text-slate-100">Name-wise performance</h3><p className="mt-1 text-[11px] text-slate-500">{computed.nameChart.column ? `${niceName(computed.metricColumn || "Records")} by ${niceName(computed.nameChart.column)}` : "Expected a Name or Customer Name column"}</p></div>
                  {computed.nameChart.data.length ? <BarChart data={computed.nameChart.data} currency={!!computed.metricColumn && /(sales|revenue|profit|amount|price|cost)/i.test(computed.metricColumn)} /> : <EmptyChart message="A Name / Customer Name field was not found. Add a Name column to display this chart." />}
                </div>
                <div className="rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6">
                  <div className="mb-5"><h3 className="text-sm font-semibold text-slate-100">Product contribution</h3><p className="mt-1 text-[11px] text-slate-500">{computed.productChart.column ? `Product share by ${niceName(computed.metricColumn || "record count")}` : "Expected a Product or Item column"}</p></div>
                  {computed.productChart.data.length ? <DistributionChart data={computed.productChart.data} /> : <EmptyChart message="A Product / Item field was not found. Add a Product column to display this chart." />}
                </div>
                <div className="rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6 xl:col-span-2">
                  <div className="mb-5"><h3 className="text-sm font-semibold text-slate-100">Category performance</h3><p className="mt-1 text-[11px] text-slate-500">{computed.categoryChart.column ? `${niceName(computed.metricColumn || "Records")} by ${niceName(computed.categoryChart.column)}` : "Expected a Category or Sub-Category column"}</p></div>
                  {computed.categoryChart.data.length ? <BarChart data={computed.categoryChart.data} currency={!!computed.metricColumn && /(sales|revenue|profit|amount|price|cost)/i.test(computed.metricColumn)} /> : <EmptyChart message="A Category / Sub-Category field was not found. Add a Category column to display this chart." />}
                </div>
                <div className="rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6 xl:col-span-2">
                  <div className="mb-3"><h3 className="text-sm font-semibold text-slate-100">Date-wise performance trend</h3><p className="mt-1 text-[11px] text-slate-500">{computed.dateColumn && computed.metricColumn ? `${niceName(computed.metricColumn)} grouped by each available date in ${niceName(computed.dateColumn)}` : "Requires a date column and a numeric business metric"}</p></div>
                  <TrendChart data={computed.trendData} />
                </div>
              </div>
            </section>

            <section className="mb-8 rounded-2xl border border-slate-800 bg-[#111b2b] p-5 md:p-6">
              <SectionTitle title="Dataset preview" subtitle={`Showing the first ${computed.preview.length} rows from ${computed.totalRecords.toLocaleString("en-IN")} records`} />
              <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-xs"><thead><tr className="border-b border-slate-700 text-slate-400">{computed.columns.map((column) => <th key={column} className="px-3 py-3 font-medium">{niceName(column)}</th>)}</tr></thead><tbody>{computed.preview.map((row, index) => <tr key={index} className="border-b border-slate-800 last:border-0">{computed.columns.map((column) => <td key={column} className="max-w-[220px] truncate px-3 py-3 text-slate-300">{row[column] || "—"}</td>)}</tr>)}</tbody></table></div>
            </section>

            <section className="mb-8 rounded-2xl border border-cyan-900/40 bg-[#101c2c] p-5 md:p-7">
              <div className="mb-5"><p className="text-[10px] font-semibold tracking-[0.2em] text-cyan-400">LANGGRAPH MULTI-AGENT SYSTEM</p><h2 className="mt-2 text-xl font-semibold text-white">Ask your business analyst</h2><p className="mt-1 text-xs text-slate-400">Ask questions about the uploaded dataset and receive data findings and practical business recommendations.</p></div>
              <form onSubmit={handleAsk} className="flex flex-col gap-3 md:flex-row"><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: Which product generated the highest sales?" className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-[#080f1c] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-500" /><button type="submit" disabled={asking || !question.trim()} className="rounded-xl bg-cyan-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50">{asking ? "Analysing…" : "Generate insights →"}</button></form>
              {asking && <p className="mt-4 text-xs text-cyan-300">AI agents are analysing your dataset…</p>}
              {(analysis || insights) && <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">{analysis && <AgentCard title="Data Analyst Agent" content={analysis} icon="▤" />}{insights && <AgentCard title="Business Insight Agent" content={insights} icon="✦" />}</div>}
              {error && <p className="mt-4 text-xs text-red-300">{error}</p>}
            </section>
          </>
        )}

        <footer className="border-t border-slate-800 py-6 text-center text-[11px] text-slate-600">AI Business Intelligence · Multi-Agent Analytics Platform · Next.js · FastAPI · Python · LangGraph · Groq</footer>
      </div>
    </main>
  );
}

function AgentCard({ title, content, icon }: { title: string; content: string; icon: string }) {
  return <article className="rounded-xl border border-slate-700 bg-[#0b1422] p-5"><div className="mb-3 flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400/10 text-lg text-cyan-300">{icon}</span><h3 className="text-sm font-semibold text-cyan-300">{title}</h3></div><div className="whitespace-pre-wrap break-words text-xs leading-6 text-slate-300">{content}</div></article>;
}
