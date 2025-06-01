/* dashboard.js – renders dashboard charts */

let posts10dChart = null;
let posts10dChannelsChart = null;
let heatmapChart = null;
let throughputLatencyChart = null;

/* Build (or update) the chart */
function drawPosts10d({ labels, counts }) {
  const ctx = document.getElementById("chartPosts10d");
  if (!ctx) {
    console.warn("#chartPosts10d canvas not found");
    return;
  }
  if (!posts10dChart) {
    posts10dChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Posts per day",
            data: counts,
            fill: false,
            tension: 0.3,
          },
        ],
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
          x: {
            ticks: {
              font: {
                size: 10, // 👈 Make date labels smaller!
              },
            },
          },
        },
        plugins: {
          tooltip: {
            enabled: false, // <<< KEY PART
            external: customTooltip, // <<< KEY PART
          },
          legend: { display: false },
        },
      },
    });
  } else {
    posts10dChart.data.labels = labels;
    posts10dChart.data.datasets[0].data = counts;
    posts10dChart.update();
  }
}

/* Build (or update) the channels chart */
function drawPosts10dChannels({ labels, series }) {
  const ctx = document.getElementById("chartPosts10dChannels");
  if (!ctx) return;
  if (posts10dChannelsChart) {
    posts10dChannelsChart.destroy();
  }
  posts10dChannelsChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: series.map((s, i) => ({
        label: s.label,
        data: s.data,
        borderColor: getColor(i),
        backgroundColor: getColor(i),
        fill: false,
        tension: 0, // <--- not smooth line
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      devicePixelRatio: 2,

      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: {
          ticks: {
            font: {
              size: 10, // 👈 Make date labels smaller!
            },
          },
        },
      },
      plugins: {
        tooltip: {
          enabled: false, // <<< KEY PART
          external: customTooltip, // <<< KEY PART
        },
        legend: { position: "top" },
      },
    },
  });
}

/* Build (or update) heatmap */
function drawHeatmap(matrix) {
  console.log("HEATMAP:", matrix);
  if (!matrix) return;
  const { data, xLabels, yLabels, max } = matrix;
  const ctx = document.getElementById("heatmapChart");
  if (!ctx) {
    console.warn("#heatmapChart canvas not found");
    return;
  }
  // destroy old chart if present
  if (heatmapChart) {
    heatmapChart.destroy();
  }
  heatmapChart = new Chart(ctx, {
    type: "matrix",
    data: {
      datasets: [
        {
          data: data,
          backgroundColor: (chartCtx) => {
            const item = chartCtx.dataset.data[chartCtx.dataIndex];
            const alpha = max ? item.v / max : 0;
            return `rgba(59,130,246,${alpha})`;
          },
        },
      ],
    },
    options: {
      scales: {
        x: { type: "category", labels: xLabels },
        y: { type: "category", labels: yLabels, reverse: true },
      },
      elements: { rectangle: { borderWidth: 1 } },
      plugins: {
        tooltip: {
          enabled: false, // <<< KEY PART
          external: customTooltipHeatmap, // <<< KEY PART
        },
        legend: { display: false },
      },
      animation: false,
    },
  });
}

function getColor(i) {
  const palette = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#14b8a6",
  ];
  return palette[i % palette.length];
}

/* Fetch summary JSON and feed the charts */
async function loadMetrics() {
  try {
    const res = await fetch("/api/metrics/summary");
    if (!res.ok) throw new Error(res.statusText);
    const json = await res.json();
    console.log(json);
    if (json.posts_10d) drawPosts10d(json.posts_10d);
    if (json.throughput_latency) drawThroughputLatency(json.throughput_latency);

    if (json.posts_10d_channels) drawPosts10dChannels(json.posts_10d_channels);
    if (json.posts_matrix) {
      drawHeatmap(json.posts_matrix);
    } else {
      console.warn("No posts_matrix data in summary");
    }
  } catch (err) {
    console.error("Metrics fetch failed:", err);
  }
}

/* Wait until DOM ready and Chart.js present */
function ready(fn) {
  if (document.readyState !== "loading") fn();
  else document.addEventListener("DOMContentLoaded", fn);
}

ready(() => {
  if (typeof Chart === "undefined") {
    console.error("Chart.js not loaded – check CDN tag order.");
    return;
  }
  loadMetrics();
  //   setInterval(loadMetrics, 30_000); // refresh every 30 s
});

function customTooltipHeatmap(context) {
    let tooltipEl = document.getElementById("chartjs-universal-tooltip");
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.id = "chartjs-universal-tooltip";
      tooltipEl.className = "chartjs-tooltip-heatmap";
      document.body.appendChild(tooltipEl);
    }
  
    const tooltip = context.tooltip;
    if (!tooltip || tooltip.opacity === 0) {
      tooltipEl.style.opacity = 0;
      return;
    }
  
    let content = "";
    if (tooltip.dataPoints && tooltip.dataPoints.length > 0) {
      const dp = tooltip.dataPoints[0];
      if (context.chart.config.type === "matrix") {
        // Use numeric y as weekday index
        const weekDays = [
          "Sunday", "Monday", "Tuesday", "Wednesday",
          "Thursday", "Friday", "Saturday"
        ];
        const pad = n => n.toString().padStart(2, "0");
        let { x, y } = dp.parsed;
        const item = dp.dataset.data[dp.dataIndex];
        // y is index: 0=Sunday ... 6=Saturday
        const yIndex = typeof y === "number" ? y : parseInt(y, 10);
        const weekday = weekDays[yIndex +1] || yIndex;
        const hourLabel = `${pad(x)}:00`;
  
        content += `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">
            <b style="margin-right:4px">${weekday} </b> <b>${hourLabel}</b>
          </div>
          <div style="border-top:1px solid #e5e7eb; margin:8px 0;"></div>
          <div style="font-weight:700; font-size:15px;">
            ${item.v} posts
          </div>
        `;
      }
    }
  
    const { offsetLeft: posX, offsetTop: posY } = tooltip.chart.canvas;
    tooltipEl.innerHTML = content;
    tooltipEl.style.opacity = 1;
    tooltipEl.style.left = `${posX + tooltip.caretX + 14}px`;
    tooltipEl.style.top = `${posY + tooltip.caretY + 14}px`;
  }
  

function customTooltip(context) {
  let tooltipEl = document.getElementById("chartjs-minimal-tooltip");
  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.id = "chartjs-minimal-tooltip";
    tooltipEl.className = "chartjs-tooltip-heatmap"; // Reuse the small CSS!
    document.body.appendChild(tooltipEl);
  }

  const tooltip = context.tooltip;
  if (!tooltip || tooltip.opacity === 0) {
    tooltipEl.style.opacity = 0;
    return;
  }

  let content = "";
  if (tooltip.dataPoints && tooltip.dataPoints.length > 0) {
    const dp = tooltip.dataPoints[0];
    // Label: day, channel, etc. Value: count
    // Try to support both line and bar configs
    let label = dp.label || dp.parsed.x || dp.parsed.y;
    let value = dp.formattedValue || (dp.raw && dp.raw.v) || dp.raw || "";
    // Remove any HTML from label just in case
    label = String(label).replace(/</g, "&lt;").replace(/>/g, "&gt;");

    content += `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <b>${label}</b> <b>${value}</b>
      </div>
    `;
  }

  const { offsetLeft: posX, offsetTop: posY } = tooltip.chart.canvas;
  tooltipEl.innerHTML = content;
  tooltipEl.style.opacity = 1;
  tooltipEl.style.left = `${posX + tooltip.caretX + 14}px`;
  tooltipEl.style.top = `${posY + tooltip.caretY + 14}px`;
}

// SLIDER ________________________
document.addEventListener("DOMContentLoaded", () => {
  const slider = document.getElementById("timeRangeDays");
  const valueSpan = document.getElementById("timeRangeValue");

  if (!slider || !valueSpan) {
    // If either element is missing, do not proceed
    if (!slider) {
      console.warn(
        "Slider element with id 'timeRangeDays' not found in DOM. The slider functionality will not work. " +
        "Ensure an element with id='timeRangeDays' exists in your HTML."
      );
    }
    if (!valueSpan) {
      console.warn(
        "Value span element with id 'timeRangeValue' not found in DOM. The slider value display will not work. " +
        "Ensure an element with id='timeRangeValue' exists in your HTML."
      );
    }
    console.warn(
      "Slider or value span not found in DOM.",
      { slider: !!slider, valueSpan: !!valueSpan }
    );
    return;
  }

  // Set initial value
  valueSpan.textContent = slider.value;

  slider.addEventListener("input", () => {
    valueSpan.textContent = slider.value;
    loadPostsPerChannelChart(parseInt(slider.value, 10));
  });

  // Initial load
  loadPostsPerChannelChart(parseInt(slider.value, 10));
});
async function loadPostsPerChannelChart(days) {
  try {
    const res = await fetch(`/api/metrics/summary?days=${days}`);
    if (!res.ok) throw new Error(res.statusText);
    const json = await res.json();
    if (json.posts_10d_channels) drawPosts10dChannels(json.posts_10d_channels);
  } catch (err) {
    console.error("Posts per Channel fetch failed:", err);
  }
}
function drawThroughputLatency({ points }) {
  const ctx = document.getElementById("chartThroughputLatency");
  if (!ctx) return;
  if (throughputLatencyChart) throughputLatencyChart.destroy();
  throughputLatencyChart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Msg size vs. translation time",
          data: points,
          pointRadius: 5,
          backgroundColor: "rgba(59,130,246,0.6)",
          borderColor: "#3b82f6",
          parsing: false, // disables default parsing for scatter
        },
      ],
    },
    options: {
      scales: {
        x: {
          title: { display: true, text: "Original size (chars)" },
          beginAtZero: true,
        },
        y: {
          title: { display: true, text: "Translation time (s)" },
          beginAtZero: true,
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const d = ctx.raw;
              return `Size: ${d.x}, Latency: ${d.y.toFixed(2)}s, Channel: ${
                d.label
              }`;
            },
          },
        },
        legend: { display: false },
      },
    },
  });
}
