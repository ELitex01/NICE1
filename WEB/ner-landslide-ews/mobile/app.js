// Register service worker + request sync on reconnect
navigator.serviceWorker.register("/sw.js");
window.addEventListener("online", () =>
  navigator.serviceWorker.ready.then(sw => sw.sync.register("sync-reports")));

// Geolocated report form
async function submitReport() {
  const pos = await new Promise((res, rej) =>
    navigator.geolocation.getCurrentPosition(res, rej, {enableHighAccuracy: true}));
  const rep = {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    report_type: document.querySelector("#reportType").value,
    severity: +document.querySelector("#severity").value,
    description: document.querySelector("#desc").value,
    device_id: getDeviceId(),
    client_ts: new Date().toISOString(),
  };

  if (navigator.onLine) {
    const r = await fetch("/api/reports", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(rep),
    });
    if (r.ok) { toast("Report sent ✓"); return; }
  }
  // Offline path — queue locally
  await queueReport(rep);
  toast("Saved offline — will sync when connected");
}

function getDeviceId() {
  let id = localStorage.getItem("device_id");
  if (!id) { id = crypto.randomUUID(); localStorage.setItem("device_id", id); }
  return id;
}

function toast(msg) {
  const el = document.createElement("div");
  el.textContent = msg;
  el.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#ff6b35;color:#fff;padding:10px 20px;border-radius:8px;z-index:999";
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}