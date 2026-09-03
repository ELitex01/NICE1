const API = "/api";
let token = localStorage.getItem("jwt") || null;
let map, heatLayer, markerLayer, choroplethLayer, geojsonData;
let districts = [];
let historyCache = {};

// ── Auth ──────────────────────────────────────────────
async function doLogin() {
  const r = await fetch(`${API}/auth/token`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({phone: phone.value, password: password.value}),
  });
  if (r.ok) {
    const j = await r.json();
    token = j.access_token;
    localStorage.setItem("jwt", token);
    loginOverlay.classList.add("hidden");
    if (["district_admin","state_admin"].includes(j.role)) adminTab.style.display = "";
    init();
  }
}
function skipLogin() { loginOverlay.classList.add("hidden"); init(); }

// ── Map ───────────────────────────────────────────────
function init() {
  map = L.map("map", {zoomControl: true}).setView([25.5, 92.5], 6);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {attribution: "©OpenStreetMap ©CARTO"}).addTo(map);

  markerLayer = L.layerGroup().addTo(map);
  loadDistricts();
  loadBoundaries();
  loadFeedStatus();
  setInterval(loadDistricts, 120_000);   // poll every 2 min
  setInterval(loadFeedStatus, 300_000);
}

async function authHeaders() {
  return token ? {Authorization: `Bearer ${token}`} : {};
}

async function loadDistricts() {
  try {
    const r = await fetch(`${API}/districts/risk`, {headers: await authHeaders()});
    districts = await r.json();
    renderMarkers();
    renderHeat();
    if (geojsonData) renderChoropleth();
  } catch (e) { console.error("districts fetch failed", e); }
}

async function loadBoundaries() {
  try {
    const r = await fetch(`${API}/districts/boundaries`);
    geojsonData = await r.json();
  } catch(e) {}
}

async function loadFeedStatus() {
  const r = await fetch(`${API}/districts/feed-status`, {headers: await authHeaders()});
  const s = await r.json();
  feedStatus.innerHTML = Object.entries(s).map(([src, {age_seconds}]) => {
    const fresh = age_seconds < 3600;
    return `<span style="font-size:11px;margin-right:10px">
      <span class="feed-dot ${fresh ? "fresh" : "stale"}"></span>${src}
      ${fresh ? "live" : Math.round(age_seconds/60)+"m stale"}
    </span>`;
  }).join("");
}

function bandColor(p) {
  return p >= 0.70 ? "#ef4444" : p >= 0.40 ? "#f59e0b" : "#22c55e";
}

function renderMarkers() {
  markerLayer.clearLayers();
  districts.forEach(d => {
    const r = 6 + d.risk * 10;
    const m = L.circleMarker([d.lat, d.lon], {
      radius: r, fillColor: bandColor(d.risk), fillOpacity: 0.85,
      color: "#fff", weight: 1, opacity: 0.4,
    });
    m.bindPopup(`<b>${d.name}</b><br>Risk: ${(d.risk*100).toFixed(0)}%<br>${d.trigger || ""}`);
    m.on("click", () => openDistrict(d));
    markerLayer.addLayer(m);
  });
}

function renderHeat() {
  if (heatLayer) map.removeLayer(heatLayer);
  const pts = districts.map(d => [d.lat, d.lon, d.risk]);
  heatLayer = L.heatLayer(pts, {
    radius: 35, blur: 25, maxZoom: 10,
    gradient: {0.2:"#22c55e", 0.5:"#f59e0b", 0.8:"#ef4444"},
  }).addTo(map);
}

function renderChoropleth() {
  if (choroplethLayer) map.removeLayer(choroplethLayer);
  const riskById = Object.fromEntries(districts.map(d => [d.district_id, d.risk]));
  choroplethLayer = L.geoJSON(geojsonData, {
    style: f => ({
      fillColor: bandColor(riskById[f.properties.id] || 0),
      fillOpacity: 0.35, color: "#fff", weight: 0.8,
    }),
    onEachFeature: (f, layer) => {
      const d = districts.find(x => x.district_id === f.properties.id);
      if (d) layer.bindPopup(`<b>${d.name}</b><br>${(d.risk*100).toFixed(0)}%`);
    },
  }).addTo(map);
}

// ── District panel ────────────────────────────────────
async function openDistrict(d) {
  sidebar.classList.add("open");
  districtName.textContent = d.name;
  riskPct.textContent = `${(d.risk*100).toFixed(0)}%`;
  riskPct.style.color = bandColor(d.risk);
  riskFill.style.width = `${d.risk*100}%`;
  riskFill.style.background = bandColor(d.risk);

  statRows.innerHTML = [
    ["Rainfall 72 h", d.rain72 ? `${d.rain72.toFixed(1)} mm` : "—"],
    ["Soil moisture", d.soilmoist ? `${(d.soilmoist*100).toFixed(0)}%` : "—"],
    ["Slope", d.slope ? `${d.slope.toFixed(1)}°` : "—"],
    ["Elevation", d.elev ? `${d.elev.toFixed(0)} m` : "—"],
    ["Model version", d.model_version || "—"],
    ["Updated", new Date(d.updated_at).toLocaleString()],
  ].map(([k,v]) => `<div class="stat-row"><span>${k}</span><span>${v}</span></div>`).join("");

  // SHAP drivers
  shapDrivers.innerHTML = (d.shap_top || []).map(s =>
    `<div style="margin-bottom:4px">
       <b>${s.feature}</b> ${s.impact > 0 ? "↑ increases" : "↓ decreases"} risk
       (${Math.abs(s.impact).toFixed(2)})
     </div>`).join("") || "No data";

  // history chart
  const hist = await fetch(
    `${API}/districts/risk/history?district_id=${d.district_id}&hours=72`,
    {headers: await authHeaders()}).then(r => r.json());
  historyCache[d.district_id] = hist;
  drawHistory(hist);
  timeSlider.value = 72;
  timeSlider.oninput = () => {
    const idx = Math.floor(timeSlider.value / 72 * (hist.length - 1));
    drawHistory(hist, idx);
  };
}

function drawHistory(hist, upto) {
  const c = document.getElementById("historyChart");
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  const data = upto ? hist.slice(0, upto + 1) : hist;
  if (!data.length) return;
  ctx.beginPath();
  data.forEach((pt, i) => {
    const x = (i / (data.length - 1)) * c.width;
    const y = c.height - pt.probability * c.height;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#ff6b35";
  ctx.lineWidth = 2;
  ctx.stroke();
  // threshold line
  ctx.setLineDash([4,4]);
  ctx.beginPath();
  ctx.moveTo(0, c.height * 0.3);
  ctx.lineTo(c.width, c.height * 0.3);
  ctx.strokeStyle = "#ef4444";
  ctx.stroke();
  ctx.setLineDash([]);
}

// ── Tab switching ─────────────────────────────────────
document.querySelectorAll(".tab").forEach(t => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    if (t.dataset.tab === "alerts") loadAlertFeed();
  };
});

async function loadAlertFeed() {
  const r = await fetch(`${API}/alerts`, {headers: await authHeaders()});
  const alerts = await r.json();
  alertFeed.innerHTML = alerts.slice(0, 30).map(a =>
    `<div class="alert-item ${a.risk_band}">
       <b>${a.transition_type}</b> · ${(a.probability*100).toFixed(0)}%
       · ${new Date(a.triggered_at).toLocaleString()}
       · ${a.recipient_count} notified
     </div>`).join("");
}