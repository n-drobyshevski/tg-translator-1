/* dashboard.js – renders dashboard charts */

let posts10dChart = null;
let posts10dChannelsChart = null;
let heatmapChart = null;

/* Build (or update) the chart */
function drawPosts10d({ labels, counts }) {
  const ctx = document.getElementById('chartPosts10d');
  if (!ctx) {
    console.warn('#chartPosts10d canvas not found');
    return;
  }
  if (!posts10dChart) {
    posts10dChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Posts per day',
          data: counts,
          fill: false,
          tension: 0.3
        }]
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } }
        },
        plugins: { legend: { display: false } }
      }
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
        tension: 0 // <--- not smooth line
      }))
    },
    options: {
      responsive: true,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
      plugins: { legend: { position: 'top' } },
    },
  });
}
  
/* Build (or update) heatmap */
function drawHeatmap(matrix) {
console.log("HEATMAP:", matrix);
  if (!matrix) return;
  const { data, xLabels, yLabels, max } = matrix;
  const ctx = document.getElementById('heatmapChart');
  if (!ctx) {
    console.warn('#heatmapChart canvas not found');
    return;
  }
  // destroy old chart if present
  if (heatmapChart) {
    heatmapChart.destroy();
  }
  heatmapChart = new Chart(ctx, {
    type: 'matrix',
    data: {
      datasets: [{
        data: data,
        backgroundColor: (chartCtx) => {
          const item = chartCtx.dataset.data[chartCtx.dataIndex];
          const alpha = max ? (item.v / max) : 0;
          return `rgba(59,130,246,${alpha})`;
        }
      }]
    },
    options: {
      scales: {
        x: { type: 'category', labels: xLabels },
        y: { type: 'category', labels: yLabels, reverse: true }
      },
      elements: { rectangle: { borderWidth: 1 } },
      plugins: {
        tooltip: {
          callbacks: {
            title: () => '',
            label: ctx => {
              const item = ctx.dataset.data[ctx.dataIndex];
              return `${ctx.parsed.y}, ${ctx.parsed.x}: ${item.v} posts`;
            }
          }
        },
        legend: { display: false }
      },
      animation: false,
    }
  });
}

function getColor(i) {
  const palette = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#14b8a6'];
  return palette[i % palette.length];
}

/* Fetch summary JSON and feed the charts */
async function loadMetrics() {
  try {
    const res = await fetch('/api/metrics/summary');
    if (!res.ok) throw new Error(res.statusText);
    const json = await res.json();
    console.log(json); 
    if (json.posts_10d) drawPosts10d(json.posts_10d);
    if (json.posts_10d_channels) drawPosts10dChannels(json.posts_10d_channels);
    if (json.posts_matrix) {
      drawHeatmap(json.posts_matrix);
    } else {
      console.warn('No posts_matrix data in summary');
    }
  } catch (err) {
    console.error('Metrics fetch failed:', err);
  }
}

/* Wait until DOM ready and Chart.js present */
function ready(fn) {
  if (document.readyState !== 'loading') fn();
  else document.addEventListener('DOMContentLoaded', fn);
}

ready(() => {
  if (typeof Chart === 'undefined') {
    console.error('Chart.js not loaded – check CDN tag order.');
    return;
  }
  loadMetrics();
//   setInterval(loadMetrics, 30_000); // refresh every 30 s
});