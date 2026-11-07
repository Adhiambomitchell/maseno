// Campus map for Maseno University using Leaflet and Geoapify.
const CATS = {
  admin:     { label: "Offices",   icon: "🏛️", color: "#E8556D" },
  lecture:   { label: "Lectures",  icon: "🎓", color: "#0B5FA5" },
  library:   { label: "Library",   icon: "📚", color: "#12A39A" },
  hostel:    { label: "Hostels",   icon: "🛏️", color: "#F7A928" },
  health:    { label: "Health",    icon: "🩺", color: "#C2418F" },
  food:      { label: "Food",      icon: "🍽️", color: "#F2762E" },
  sports:    { label: "Sports",    icon: "⚽", color: "#2FB57A" },
  transport: { label: "Transport", icon: "🚌", color: "#6B5BD6" },
  hotel:     { label: "Hotels",    icon: "🏨", color: "#083F6E" },
};

let map, places = [], markers = {}, selected = null, youMarker = null, routeLine = null;
let active = new Set(Object.keys(CATS).filter(c => c !== "hotel"));

function buildChips() {
  const el = document.getElementById("chips");
  el.innerHTML = "";
  Object.entries(CATS).forEach(([k, c]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (active.has(k) ? " on" : "");
    b.textContent = `${c.icon} ${c.label}`;
    b.onclick = () => {
      active.has(k) ? active.delete(k) : active.add(k);
      buildChips(); render();
    };
    el.appendChild(b);
  });
}

function render() {
  const list = document.getElementById("placeList");
  list.innerHTML = "";
  const visible = places.filter(p => active.has(p.cat));
  
  // Show/hide markers on Leaflet map
  places.forEach(p => {
    const marker = markers[p.id];
    if (marker) {
      if (active.has(p.cat)) {
        if (!map.hasLayer(marker)) marker.addTo(map);
      } else {
        if (map.hasLayer(marker)) map.removeLayer(marker);
      }
    }
  });

  visible.forEach(p => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "place" + (selected && selected.id === p.id ? " sel" : "");
    b.innerHTML = `<b>${CATS[p.cat].icon} ${esc(p.name)}</b><small>${esc(p.desc)}</small>`;
    b.onclick = () => select(p.id, true);
    list.appendChild(b);
  });

  if (!visible.length) list.innerHTML = '<p class="muted" style="padding:16px">Turn on a category above to see places.</p>';
}

function select(id, pan) {
  selected = places.find(p => p.id === id);
  if (!selected) return;
  if (!active.has(selected.cat)) { active.add(selected.cat); buildChips(); }
  render();
  
  const marker = markers[id];
  if (marker) {
    if (pan) {
      map.setView([selected.lat, selected.lng], 17);
    }
    marker.openPopup();
  }

  const box = document.getElementById("directions");
  box.style.display = "block";
  box.innerHTML = `<b>${esc(selected.name)}</b><p style="margin:6px 0 14px">${esc(selected.desc)}</p>` +
    `<button class="btn small" id="walkSide" type="button">Walk me there</button>`;
  document.getElementById("walkSide").onclick = () => walkTo(selected);
}

function walkTo(p) {
  const box = document.getElementById("directions");
  box.style.display = "block";
  box.innerHTML = "Finding your location…";
  if (!navigator.geolocation) { 
    box.innerHTML = `Your browser can't share location. <a target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking">Open directions</a>.`; 
    return; 
  }
  navigator.geolocation.getCurrentPosition(
    pos => {
      const from = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      route(from, p);
    },
    () => { box.innerHTML = `Location is blocked. Allow it in your browser settings.`; },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function route(from, p) {
  const box = document.getElementById("directions");
  if (youMarker) map.removeLayer(youMarker);
  
  // Add "You are here" marker
  const youIcon = L.divIcon({
    className: 'custom-you-marker',
    html: '<div style="background:#0B5FA5;width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 0 5px rgba(0,0,0,0.3);"></div>',
    iconSize: [16, 16]
  });
  youMarker = L.marker([from.lat, from.lng], { icon: youIcon }).addTo(map).bindPopup("You are here");

  if (routeLine) map.removeLayer(routeLine);
  routeLine = L.polyline([[from.lat, from.lng], [p.lat, p.lng]], { color: '#E8556D', weight: 5, opacity: 0.8 }).addTo(map);
  
  const bounds = L.latLngBounds([[from.lat, from.lng], [p.lat, p.lng]]);
  map.fitBounds(bounds, { padding: [50, 50] });

  const link = `<a class="btn small ghost" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking">Open in Google Maps</a>`;
  box.innerHTML = `<b>${esc(p.name)}</b><br>🚶 Direct route mapped.<p style="margin-top:14px">${link}</p>`;
}

function esc(s) { 
  const d = document.createElement("div"); 
  d.textContent = s == null ? "" : s; 
  return d.innerHTML; 
}

(async function init() {
  const res = await fetch("/api/places");
  const data = await res.json();
  
  // Initialize Leaflet Map centered at Campus
  map = L.map('map').setView([window.CAMPUS.lat, window.CAMPUS.lng], 16);

  // Add Geoapify tile layer
  const apiKey = window.MAPS_KEY || '';
  const tileUrl = apiKey 
    ? `https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=${apiKey}`
    : `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`;

  L.tileLayer(tileUrl, {
    attribution: 'Powered by <a href="https://www.geoapify.com/" target="_blank">Geoapify</a> | © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 20
  }).addTo(map);

  places = data.map(l => ({ 
    id: l.slug || "p" + l.id, 
    slug: l.slug, 
    name: l.name, 
    cat: CATS[l.category] ? l.category : "lecture",
    lat: l.lat, 
    lng: l.lng, 
    desc: l.description, 
    query: l.query, 
    verified: !!l.verified 
  }));

  places.forEach(p => {
    const c = CATS[p.cat] || CATS["lecture"];
    const customIcon = L.divIcon({
      className: 'custom-map-marker',
      html: `<div style="background:${c.color};color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;border:2px solid white;box-shadow:0 3px 6px rgba(0,0,0,0.3);">${c.icon}</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    const m = L.marker([p.lat, p.lng], { icon: customIcon })
      .bindPopup(`<div style="max-width:200px;font-family:'Nunito Sans',sans-serif"><b>${esc(p.name)}</b><br><small>${esc(p.desc)}</small></div>`);
    
    m.on('click', () => select(p.id, false));
    markers[p.id] = m;
  });

  buildChips();
  render();

  const want = new URLSearchParams(location.search).get("loc");
  if (want) select(want, true);
})();
