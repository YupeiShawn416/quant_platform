(function () {
  const seriesConfig = [
    { key: "strategy_nav", label: "策略净值", color: "#0f766e" },
    { key: "benchmark_nav", label: "基准净值", color: "#2563eb" },
    { key: "excess_nav", label: "超额净值", color: "#9333ea" },
    { key: "drawdown", label: "回撤", color: "#b42318" },
  ];

  function parseData(el) {
    try {
      return JSON.parse(el.dataset.chart || "[]");
    } catch (_error) {
      return [];
    }
  }

  function toNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function buildPath(rows, key, width, height, padding, min, max) {
    const points = rows
      .map((row, index) => {
        const value = toNumber(row[key]);
        if (value === null) return null;
        const x = padding + (index / Math.max(rows.length - 1, 1)) * (width - padding * 2);
        const y = height - padding - ((value - min) / Math.max(max - min, 0.000001)) * (height - padding * 2);
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .filter(Boolean);
    return points.length ? `M ${points.join(" L ")}` : "";
  }

  function renderChart(el) {
    const rows = parseData(el);
    if (!rows.length) {
      el.innerHTML = '<div class="empty-table">暂无净值数据</div>';
      return;
    }
    const width = 960;
    const height = el.classList.contains("large") ? 390 : 280;
    const padding = 34;
    const values = [];
    rows.forEach((row) => {
      seriesConfig.forEach((series) => {
        const value = toNumber(row[series.key]);
        if (value !== null) values.push(value);
      });
    });
    const min = Math.min(...values);
    const max = Math.max(...values);
    const legend = seriesConfig
      .map((series) => `<span class="legend-item"><span class="legend-color" style="background:${series.color}"></span>${series.label}</span>`)
      .join("");
    const paths = seriesConfig
      .map((series) => {
        const path = buildPath(rows, series.key, width, height, padding, min, max);
        if (!path) return "";
        return `<path d="${path}" fill="none" stroke="${series.color}" stroke-width="2.2" vector-effect="non-scaling-stroke"></path>`;
      })
      .join("");
    const grid = [0, 0.25, 0.5, 0.75, 1]
      .map((ratio) => {
        const y = padding + ratio * (height - padding * 2);
        return `<line x1="${padding}" x2="${width - padding}" y1="${y}" y2="${y}" stroke="#e5e7eb"></line>`;
      })
      .join("");
    el.innerHTML = `
      <div class="chart-legend">${legend}</div>
      <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="backtest nav chart">
        ${grid}
        <line x1="${padding}" x2="${padding}" y1="${padding}" y2="${height - padding}" stroke="#cbd5e1"></line>
        <line x1="${padding}" x2="${width - padding}" y1="${height - padding}" y2="${height - padding}" stroke="#cbd5e1"></line>
        ${paths}
      </svg>
    `;
  }

  document.querySelectorAll("[data-chart]").forEach(renderChart);
})();
