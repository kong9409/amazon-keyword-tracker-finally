(() => {
  const $ = (id) => document.getElementById(id);
  const form = $("captureForm");
  const runButton = $("runCapture");
  const historyBody = $("historyBody");
  const sourceBadge = $("sourceBadge");
  const ownerId = getOwnerId();
  let jobTimer = null;

  const tableFields = [
    "date", "asin", "keyword", "traffic_share", "aba_rank", "search_volume",
    "organic_position", "ad_position", "price", "coupon_value", "deal_price",
    "prime_discount_price", "estimated_sales", "product_rank", "rating",
    "review_count", "product_url", "status", "message"
  ];

  function getOwnerId() {
    const saved = localStorage.getItem("keywordTrackerOwnerId");
    if (saved && /^[A-Za-z0-9_-]{16,100}$/.test(saved)) return saved;
    const bytes = new Uint8Array(18);
    crypto.getRandomValues(bytes);
    const id = `browser_${Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("")}`;
    localStorage.setItem("keywordTrackerOwnerId", id);
    return id;
  }

  function toast(message, isError = false) {
    const node = $("toast");
    node.textContent = message;
    node.style.background = isError ? "#9a3412" : "#102a43";
    node.classList.add("show");
    window.clearTimeout(node._hideTimer);
    node._hideTimer = window.setTimeout(() => node.classList.remove("show"), 4200);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  async function api(url, options = {}) {
    const response = await fetch(url, { cache: "no-store", ...options });
    let payload;
    try { payload = await response.json(); }
    catch (_) { throw new Error(`服务返回异常（HTTP ${response.status}）`); }
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `请求失败（HTTP ${response.status}）`);
    return payload;
  }

  function showConnectionFields() {
    const isMcp = $("sorftimeMode").value === "mcp_url";
    $("cliAccountField").hidden = isMcp;
    $("mcpUrlField").hidden = !isMcp;
    $("mcpTokenField").hidden = !isMcp;
    setConnectionState("disconnected", isMcp ? "填写 MCP URL 和 Token" : "填写 Sorftime Account-SK");
  }

  function showOutputFields() {
    const mode = $("outputMode").value;
    const needsFeishu = mode === "lark" || mode === "both";
    const hasExcel = mode === "excel" || mode === "both";
    $("feishuFields").hidden = !needsFeishu;
    [$("feishuAppId"), $("feishuAppSecret"), $("feishuBaseUrl")].forEach(input => {
      input.required = needsFeishu;
    });

    const checkbox = $("autoDownload");
    const card = $("autoDownloadCard");
    if (!hasExcel) {
      checkbox.dataset.previousChecked = String(checkbox.checked);
      checkbox.checked = false;
      checkbox.disabled = true;
      card.classList.add("is-disabled");
    } else {
      checkbox.disabled = false;
      if (checkbox.dataset.previousChecked === "true") checkbox.checked = true;
      card.classList.remove("is-disabled");
    }
  }

  function setConnectionState(state, detail) {
    const connected = state === "connected";
    const testing = state === "testing";
    sourceBadge.textContent = connected ? "Sorftime 已连接" : (testing ? "正在测试连接" : "Sorftime 未连接");
    sourceBadge.className = `source-pill ${connected ? "source-on" : (testing ? "source-testing" : "source-off")}`;
    $("connectionStatus").textContent = detail || "";
    $("connectionStatus").className = `connection-status ${connected ? "connection-ok" : ""}`;
  }

  function connectionFormData() {
    const data = new FormData();
    data.set("owner_id", ownerId);
    data.set("sorftime_mode", $("sorftimeMode").value);
    data.set("sorftime_cli_account_sk", $("sorftimeCliAccountSk").value.trim());
    data.set("sorftime_mcp_url", $("sorftimeMcpUrl").value.trim());
    data.set("sorftime_mcp_token", $("sorftimeMcpToken").value.trim());
    data.set("remember_connection", "false");
    return data;
  }

  function captureFormData() {
    const data = new FormData(form);
    data.set("owner_id", ownerId);
    data.set("outputMode", $("outputMode").value);
    data.set("auto_download", (!$("autoDownload").disabled && $("autoDownload").checked) ? "true" : "false");
    data.set("daily_enabled", "false");
    data.set("remember_connection", "false");
    return data;
  }

  async function testConnection() {
    const button = $("testConnection");
    button.disabled = true;
    const cliMode = $("sorftimeMode").value === "cli_account";
    setConnectionState("testing", cliMode ? "正在验证 Account-SK…" : "正在初始化 MCP…");
    try {
      const payload = await api("/api/connection/test", { method: "POST", body: connectionFormData() });
      const info = payload.connection || {};
      const source = info.source === "sorftime_cli" ? "CLI" : "MCP";
      const count = Array.isArray(info.recognized_tools) ? info.recognized_tools.length : Number(info.tool_count || 0);
      setConnectionState("connected", `工具连接成功：${source}，识别接口 ${count} 个；数据权限将在抓取时验证，用时 ${Number(info.elapsed_seconds || 0).toFixed(2)} 秒`);
      toast("Sorftime 工具连接成功，数据权限将在抓取时验证");
    } catch (error) {
      setConnectionState("disconnected", error.message);
      toast(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function downloadFile(url) {
    if (!url) return;
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  function setProgress(job) {
    const statusText = {
      queued: "任务排队中", running: "正在抓取关键词数据", saving: "正在输出结果",
      completed: "抓取完成", completed_with_warning: "抓取完成（有提示）", failed: "任务失败"
    }[job.status] || "任务处理中";
    const percent = Number(job.percent || 0);
    $("progressTitle").textContent = statusText;
    const larkMessage = job.lark && job.lark.message ? job.lark.message : "";
    $("progressSub").textContent = job.error || larkMessage || (["completed", "completed_with_warning"].includes(job.status) ? "结果已生成。" : "正在调用 Sorftime Amazon 数据接口。");
    $("progressPct").textContent = `${percent}%`;
    $("progressFill").style.width = `${Math.max(0, Math.min(100, percent))}%`;
    $("mcpCalls").textContent = String(job.mcp_calls || 0);
    $("elapsedTime").textContent = `${Number(job.elapsed_seconds || 0).toFixed(2)} 秒`;
    $("doneCount").textContent = `${job.done || 0} / ${job.total || 0}`;
    $("recordCount").textContent = String(job.records_count || 0);
    const toolSummary = Object.entries(job.tool_calls || {}).map(([name, count]) => `${name}: ${count}`).join(" · ");
    const logs = Array.isArray(job.logs) ? job.logs.join("\n") : "暂无运行日志";
    $("logBox").textContent = toolSummary ? `${logs}\n\n接口调用：${toolSummary}` : logs;
    $("logBox").scrollTop = $("logBox").scrollHeight;
    const links = [];
    if (job.excel) links.push(`<a href="${escapeHtml(job.excel)}" download>下载 Excel</a>`);
    if (job.lark && job.lark.message) {
      const cls = job.lark.ok ? "lark-result" : "lark-result lark-error";
      links.push(`<span class="${cls}">${escapeHtml(job.lark.message)}</span>`);
    }
    $("resultLinks").innerHTML = links.join("");
  }

  function renderRows(records) {
    if (!records.length) {
      historyBody.innerHTML = '<tr><td colspan="19" class="empty">暂无结果</td></tr>';
      return;
    }
    historyBody.innerHTML = records.map(record => {
      const cells = tableFields.map(field => {
        const value = record[field] ?? "";
        if (field === "product_url" && value) return `<td><a href="${escapeHtml(value)}" target="_blank" rel="noopener">打开链接</a></td>`;
        if (field === "status") {
          const normalized = String(value).toLowerCase();
          const cls = ["success", "ok"].includes(normalized) ? "status-ok" : (normalized === "partial" ? "status-warning" : "status-failed");
          return `<td class="${cls}">${escapeHtml(value || "-")}</td>`;
        }
        return `<td title="${escapeHtml(value)}">${escapeHtml(value)}</td>`;
      }).join("");
      return `<tr>${cells}</tr>`;
    }).join("");
  }

  async function loadHistory(showToast = false) {
    try {
      const payload = await api(`/api/history?owner_id=${encodeURIComponent(ownerId)}`);
      renderRows(payload.records || []);
      if (showToast) toast("结果已刷新");
    } catch (error) {
      if (showToast) toast(error.message, true);
    }
  }

  async function pollJob(jobId) {
    window.clearTimeout(jobTimer);
    try {
      const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      const job = payload.job;
      setProgress(job);
      if (["completed", "completed_with_warning"].includes(job.status)) {
        runButton.disabled = false;
        runButton.textContent = "开始抓取";
        const results = await api(`/api/jobs/${encodeURIComponent(jobId)}/results`);
        renderRows(results.records || []);
        if (job.auto_download && job.excel) downloadFile(job.excel);
        if (job.lark && !job.lark.ok) {
          toast(`抓取完成，但飞书写入失败：${job.lark.message || "请检查配置"}`, true);
        } else if (job.auto_download && job.excel && job.lark && job.lark.ok) {
          toast("抓取完成，Excel 已下载并写入飞书");
        } else if (job.auto_download && job.excel) {
          toast("抓取完成，Excel 已开始下载");
        } else if (job.lark && job.lark.ok) {
          toast("抓取完成，数据已写入飞书");
        } else {
          toast("抓取完成");
        }
        return;
      }
      if (job.status === "failed") {
        runButton.disabled = false;
        runButton.textContent = "开始抓取";
        toast(job.error || "任务失败", true);
        return;
      }
      jobTimer = window.setTimeout(() => pollJob(jobId), 900);
    } catch (error) {
      runButton.disabled = false;
      runButton.textContent = "开始抓取并导出";
      toast(error.message, true);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    runButton.disabled = true;
    runButton.textContent = "任务创建中…";
    $("resultLinks").innerHTML = "";
    setProgress({ status: "queued", percent: 1, done: 0, total: 0, logs: ["正在提交任务…"] });
    try {
      const payload = await api("/api/jobs", { method: "POST", body: captureFormData() });
      setProgress(payload.job);
      runButton.textContent = "正在抓取…";
      pollJob(payload.job.id);
    } catch (error) {
      runButton.disabled = false;
      runButton.textContent = "开始抓取并导出";
      toast(error.message, true);
    }
  });

  $("testConnection").addEventListener("click", testConnection);
  $("sorftimeMode").addEventListener("change", showConnectionFields);
  $("outputMode").addEventListener("change", showOutputFields);
  $("refreshHistory").addEventListener("click", () => loadHistory(true));

  async function initialize() {
    try {
      const health = await api("/api/health");
      if (!health.ok) throw new Error("服务未就绪");
    } catch (error) {
      toast(`服务检查失败：${error.message}`, true);
    }
    showConnectionFields();
    showOutputFields();
    await loadHistory(false);
  }

  initialize();
})();
