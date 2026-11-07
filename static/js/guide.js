document.addEventListener("change", async e => {
  const box = e.target.closest("input[data-item]");
  if (!box) return;
  const label = box.closest(".check");
  try {
    const r = await fetch("/guide/toggle", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content }, body: JSON.stringify({ item: box.dataset.item }) });
    const d = await r.json();
    label.classList.toggle("done", d.on);
    document.getElementById("checkCount").textContent = d.count;
    document.getElementById("checkBar").style.width = Math.round(d.count / d.total * 100) + "%";
  } catch (err) { box.checked = !box.checked; }
});
