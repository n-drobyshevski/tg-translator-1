// -----------------------------
// Redesigned Edit Modal Logic
// -----------------------------
let currentEventObj = null;

function showEditModal(eventObj) {
  console.log("showEditModal called with eventObj:", eventObj);
  currentEventObj = eventObj;
  // Populate fields
  document.getElementById("field-timestamp").value = eventObj.timestamp
    ? new Date(eventObj.timestamp).toISOString().slice(0, -1)
    : "";
  document.getElementById("field-event").value = eventObj.event || "";
  document.getElementById("field-edit_timestamp").value =
    eventObj.edit_timestamp
      ? new Date(eventObj.edit_timestamp).toISOString().slice(0, -1)
      : "";
  document.getElementById("field-source_channel").value =
    eventObj.source_channel || "";
  document.getElementById("field-source_channel_name").value =
    eventObj.source_channel_name || "";
  document.getElementById("field-dest_channel").value =
    eventObj.dest_channel || "";
  document.getElementById("field-dest_channel_name").value =
    eventObj.dest_channel_name || "";
  document.getElementById("field-message_id").value = eventObj.message_id || "";
  document.getElementById("field-dest_message_id").value = eventObj.dest_message_id || "";
  document.getElementById("field-media_type").value = eventObj.media_type || "";
  document.getElementById("field-file_size_bytes").value =
    eventObj.file_size_bytes ?? "";
  document.getElementById("field-original_size").value =
    eventObj.original_size ?? "";
  document.getElementById("field-translated_size").value =
    eventObj.translated_size ?? "";
  document.getElementById("field-translation_time").value =
    eventObj.translation_time ?? "";
  document.getElementById("field-retry_count").value =
    eventObj.retry_count ?? "";
  const toggle = document.getElementById("field-posting_success");
  toggle.checked = eventObj.posting_success === true;
  document.getElementById("success-status").textContent =
    eventObj.posting_success ? "OK" : "FAIL";
  document.getElementById("field-api_error_code").value =
    eventObj.api_error_code ?? "";
  document.getElementById("field-exception_message").value =
    eventObj.exception_message || "";
  document.getElementById("field-previous_size").value =
    eventObj.previous_size ?? "";
  document.getElementById("field-new_size").value = eventObj.new_size ?? "";

  // Show modal
  openModal("edit-modal");
}

function saveEdit() {
  if (!currentEventObj) return;

  const form = document.getElementById("edit-event-form");
  const data = new FormData(form);
  const updated = {
    ...currentEventObj,
    timestamp: data.get("timestamp")
      ? new Date(data.get("timestamp")).toISOString()
      : null,
    event: data.get("event"),
    edit_timestamp: data.get("edit_timestamp")
      ? new Date(data.get("edit_timestamp")).toISOString()
      : null,
    source_channel_name: data.get("source_channel_name"),
    dest_channel_name: data.get("dest_channel_name"),
    media_type: data.get("media_type"),
    file_size_bytes: data.get("file_size_bytes")
      ? Number(data.get("file_size_bytes"))
      : null,
    original_size: data.get("original_size")
      ? Number(data.get("original_size"))
      : null,
    translated_size: data.get("translated_size")
      ? Number(data.get("translated_size"))
      : null,
    translation_time: data.get("translation_time")
      ? parseFloat(data.get("translation_time"))
      : null,
    retry_count: data.get("retry_count")
      ? Number(data.get("retry_count"))
      : null,
    posting_success: form.querySelector("#field-posting_success").checked,
    api_error_code: data.get("api_error_code")
      ? Number(data.get("api_error_code"))
      : null,
    exception_message: data.get("exception_message"),
    previous_size: data.get("previous_size")
      ? Number(data.get("previous_size"))
      : null,
    new_size: data.get("new_size") ? Number(data.get("new_size")) : null,
    message_id: data.get("message_id"),
    dest_message_id: data.get("dest_message_id"),
  };

  fetch("/admin/events/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  })
    .then((r) => {
      if (!r.ok) throw new Error("Save failed");
      return r.json();
    })
    .then((data) => {
      if (data.status === "ok") {
        window.location.reload();
      } else {
        throw new Error("Save failed");
      }
    })
    .catch((e) => alert(e));
}

// Update "OK/FAIL" label whenever toggle changes
document.addEventListener("input", function (e) {
  if (e.target && e.target.id === "field-posting_success") {
    document.getElementById("success-status").textContent = e.target.checked
      ? "OK"
      : "FAIL";
  }
});
