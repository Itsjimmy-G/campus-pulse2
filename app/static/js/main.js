async function joinEvent(eventId, csrfToken) {
  try {
    const res = await fetch(`/register_event/${eventId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    const btn = document.querySelector(`[data-join-button][data-event-id="${eventId}"]`);
    const counter = document.querySelector(`[data-spots-left][data-event-id="${eventId}"]`);
    if (data.status === "success") {
      if (btn) {
        btn.textContent = "You're In!";
        btn.classList.remove("bg-indigo-600", "hover:bg-indigo-700");
        btn.classList.add("bg-green-600");
        btn.disabled = true;
      }
      if (counter) {
        counter.textContent = `${data.spots_left} spots left`;
      }
    } else {
      alert(data.message || "Registration failed.");
    }
  } catch (e) {
    alert("Network error. Please try again.");
  }
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-join-button]");
  if (!btn) return;
  const eventId = parseInt(btn.getAttribute("data-event-id"), 10);
  const csrfToken = btn.getAttribute("data-csrf") || "";
  if (!Number.isFinite(eventId) || !csrfToken) {
    alert("Unable to register: missing event id or token.");
    return;
  }
  joinEvent(eventId, csrfToken);
});
