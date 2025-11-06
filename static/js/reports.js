function generateReport() {
  const start = document.getElementById("reportStartDate").value;
  const end = document.getElementById("reportEndDate").value;
  const status = document.getElementById("reportStatusFilter").value;
  if (start && end && end < start) {
    alert("End date cannot be earlier than start date!");
    return;
  }
  if (start && end > new Date()) {
    alert("End date cannot be in the future!");
    return;
  }
  fetch("/user/reports")
    .then(res => res.json())
    .then(data => {
      const startDate = start ? new Date(start) : null;
      const endDate = end ? new Date(end) : null;
      const issues = data.reports.filter(issue => {
        let valid = true;
        if (status !== "All" && issue.status !== status) {
          valid = false;
        }
        const issueDate = new Date(issue.timestamp);
        if (startDate && issueDate < startDate) {
          valid = false;
        }
        if (endDate && issueDate > endDate) {
          valid = false;
        }
        return valid;
      });

      const container = document.getElementById("reportContent");
      if (issues.length === 0) {
        container.innerHTML = "<p>No issues found for the selected criteria.</p>";
        document.getElementById("reportOutput").style.display = "block";
        return;
      }
      container.innerHTML = issues.map(i => `
        <div class="report-item">
          <h4>${i.type || "Unknown Issue"}</h4>
          <p>${i.description || "No description available"}</p>
          <small>${formatDate(i.timestamp)}</small>
        </div>
      `).join("");

      document.getElementById("reportOutput").style.display = "block";
    })
    .catch(err => console.error("Report error:", err));
}

function formatDate(ts) {
  if (!ts) return "N/A";
  if (ts._seconds) return new Date(ts._seconds * 1000).toLocaleString();
  if (typeof ts === "string" || typeof ts === "number") return new Date(ts).toLocaleString();
  return "N/A";
}
