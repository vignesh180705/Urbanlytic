function generateReport() {
  const start = document.getElementById("reportStartDate").value;
  const end = document.getElementById("reportEndDate").value;
  const status = document.getElementById("reportStatusFilter").value;

  fetch("/history")
    .then(res => res.json())
    .then(data => {
      const issues = data.incidents.filter(issue => {
        let valid = true;
        if (status !== "All" && issue.status !== status) valid = false;
        return valid;
      });

      const container = document.getElementById("reportContent");
      container.innerHTML = issues.map(i => `
        <div class="report-item">
          <h4>${i.category}</h4>
          <p>${i.summary}</p>
          <small>${i.timestamp}</small>
        </div>
      `).join("");

      document.getElementById("reportOutput").style.display = "block";
    })
    .catch(err => console.error("Report error:", err));
}
