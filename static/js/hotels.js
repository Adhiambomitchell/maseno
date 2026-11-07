// Infinite scrolling dynamic hotel loader using Geoapify Places API
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("hotels");
  const status = document.getElementById("hotelStatus");
  const spinner = document.getElementById("loadMoreSpinner");

  if (!container) return;

  const apiKey = window.MAPS_KEY || "";
  const center = window.CAMPUS || { lat: -0.0048, lng: 34.6005 };

  let offset = 0;
  const limit = 10;
  let isLoading = false;
  let hasMore = true;
  let totalLoaded = 0;

  // Static local fallback items to ensure content is always visible
  const staticFallback = [
    { name: "Maseno University Guest House", cat: "University Accommodation", desc: "Located within the main campus. Clean and secure for students and visitors." },
    { name: "Vientiane Resort Maseno", cat: "Hotel & Restaurant", desc: "Popular hospitality spot near Maseno town offering dining and lodging." },
    { name: "Jumuia Guest House Maseno", cat: "Guest House", desc: "Quiet environment situated near the Kisumu-Busia highway." },
    { name: "Planet Hotel Maseno", cat: "Hotel", desc: "Affordable rooms and meals located around Maseno township." }
  ];

  async function fetchHotels() {
    if (isLoading || !hasMore) return;
    isLoading = true;
    if (spinner) spinner.style.display = "block";

    // Fallback if no Geoapify key is configured
    if (!apiKey) {
      renderStaticFallback();
      if (spinner) spinner.style.display = "none";
      isLoading = false;
      hasMore = false;
      return;
    }

    const categories = "accommodation.hotel,accommodation.hostel,accommodation.guest_house";
    const url = `https://api.geoapify.com/v2/places?categories=${categories}&filter=circle:${center.lng},${center.lat},15000&bias=proximity:${center.lng},${center.lat}&limit=${limit}&offset=${offset}&apiKey=${apiKey}`;

    try {
      const response = await fetch(url);
      const data = await response.json();

      if (!data.features || data.features.length === 0) {
        hasMore = false;
        if (totalLoaded === 0) {
          renderStaticFallback();
        } else {
          status.textContent = `Showing all ${totalLoaded} places found nearby.`;
        }
      } else {
        const places = data.features;
        totalLoaded += places.length;
        offset += limit;

        places.forEach(place => {
          const props = place.properties;
          const name = props.name || props.street || "Accommodation Spot";
          const cat = props.categories ? props.categories[0].replace('accommodation.', '').replace('_', ' ') : 'Lodging';
          const address = props.formatted || "Maseno Area";

          const card = document.createElement("div");
          card.className = "card hotel-card";
          card.style.cssText = "margin-bottom:20px; padding:20px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.1);";
          card.innerHTML = `
            <div style="font-size: 28px; margin-bottom: 8px;">🏨</div>
            <div class="body">
              <h3 style="margin: 0 0 6px 0; color: #0B5FA5;">${escapeHtml(name)}</h3>
              <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 10px; text-transform: capitalize;">${escapeHtml(cat)}</span>
              <p class="muted" style="color: #4a5568; margin: 0 0 16px 0; font-size: 14px;">📍 ${escapeHtml(address)}</p>
              <div class="acts" style="display: flex; gap: 10px;">
                <a class="btn small" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + ' Maseno')}" style="background: #0B5FA5; color: white; padding: 8px 14px; border-radius: 4px; text-decoration: none; font-size: 13px;">View Map & Directions</a>
              </div>
            </div>
          `;
          container.appendChild(card);
        });

        status.textContent = `Loaded ${totalLoaded} places near campus. Scroll down for more...`;
      }
    } catch (err) {
      if (totalLoaded === 0) renderStaticFallback();
      hasMore = false;
    } finally {
      isLoading = false;
      if (spinner) spinner.style.display = "none";
    }
  }

  function renderStaticFallback() {
    status.textContent = "Showing verified accommodation spots near campus.";
    container.innerHTML = staticFallback.map(h => `
      <div class="card hotel-card" style="margin-bottom: 20px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff;">
        <div style="font-size: 28px; margin-bottom: 8px;">🏨</div>
        <div class="body">
          <h3 style="margin: 0 0 6px 0; color: #0B5FA5;">${h.name}</h3>
          <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 10px;">${h.cat}</span>
          <p class="muted" style="color: #4a5568; margin: 0 0 16px 0; font-size: 14px;">${h.desc}</p>
          <a class="btn small" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(h.name + ' Maseno')}" style="background: #0B5FA5; color: white; padding: 8px 14px; border-radius: 4px; text-decoration: none; font-size: 13px;">View Map & Directions</a>
        </div>
      </div>
    `).join("");
  }

  function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag));
  }

  // Initial load
  fetchHotels();

  // Scroll listener for infinite scrolling
  window.addEventListener("scroll", () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 300) {
      fetchHotels();
    }
  });
});