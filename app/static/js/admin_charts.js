function setChartDefaults() {
  const fontFamily = "'Inter', 'Geist', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif";
  Chart.defaults.color = "#cbd5e1";
  Chart.defaults.font.family = fontFamily;
  Chart.defaults.plugins.tooltip.backgroundColor = "rgba(30, 41, 59, 0.9)";
  Chart.defaults.plugins.tooltip.titleColor = "#e2e8f0";
  Chart.defaults.plugins.tooltip.bodyColor = "#e2e8f0";
}

function gradient(ctx, color) {
  const g = ctx.createLinearGradient(0, 0, 0, 300);
  g.addColorStop(0, color);
  g.addColorStop(1, "rgba(0,0,0,0)");
  return g;
}

function initRegistrationTrends(data) {
  const el = document.getElementById("regTrendsChart");
  if (!el) return;
  const ctx = el.getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [
        {
          label: "Registrations",
          data: data.series,
          borderColor: "#06b6d4",
          backgroundColor: gradient(ctx, "rgba(6,182,212,0.3)"),
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: "rgba(148,163,184,0.2)" }, beginAtZero: true },
      },
    },
  });
}

function initCategoryPopularity(data) {
  const el = document.getElementById("categoryChart");
  if (!el) return;
  const ctx = el.getContext("2d");
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.labels,
      datasets: [
        {
          data: data.counts,
          backgroundColor: ["#06b6d4", "#10b981", "#0ea5e9", "#f59e0b", "#ef4444"].slice(0, data.labels.length),
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#cbd5e1" } },
      },
    },
  });
}

function initHeatmap(data) {
  const el = document.getElementById("heatmapChart");
  if (!el) return;
  const ctx = el.getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.labels,
      datasets: [
        {
          label: "Capacity",
          data: data.capacity,
          backgroundColor: "rgba(148,163,184,0.5)",
          borderRadius: 6,
        },
        {
          label: "Attendance",
          data: data.attendance,
          backgroundColor: "rgba(16,185,129,0.7)",
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: "rgba(148,163,184,0.2)" }, beginAtZero: true },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (!window.analyticsData) {
    const el = document.getElementById("analytics-payload");
    if (el && el.textContent) {
      try {
        window.analyticsData = JSON.parse(el.textContent);
      } catch (e) {
        console.error("Failed to parse analytics payload JSON:", e);
        return;
      }
    } else {
      return;
    }
  }
  if (typeof Chart === "undefined") {
    console.warn("Chart.js not loaded; analytics charts will not render.");
    return;
  }
  setChartDefaults();
  initRegistrationTrends(window.analyticsData.trends);
  initCategoryPopularity(window.analyticsData.categories);
  initHeatmap(window.analyticsData.heatmap);
});
