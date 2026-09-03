function openDB() {
  return new Promise((res, rej) => {
    const req = indexedDB.open("ner_ews_local", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      db.createObjectStore("reports", {keyPath: "id"});
      db.createObjectStore("cache", {keyPath: "key"});
    };
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}

async function queueReport(rep) {
  const db = await openDB();
  rep.id = crypto.randomUUID();
  return new Promise((res, rej) => {
    const tx = db.transaction("reports", "readwrite");
    tx.objectStore("reports").put(rep);
    tx.oncomplete = () => res(rep.id);
  });
}

async function getAllPending(db) {
  return new Promise(res => {
    const req = db.transaction("reports").objectStore("reports").getAll();
    req.onsuccess = () => res(req.result.filter(r => !r.synced_at));
  });
}

async function markSynced(db, id) {
  const tx = db.transaction("reports", "readwrite");
  const store = tx.objectStore("reports");
  const req = store.get(id);
  req.onsuccess = () => {
    req.result.synced_at = new Date().toISOString();
    store.put(req.result);
  };
}