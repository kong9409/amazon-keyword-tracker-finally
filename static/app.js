const form = document.querySelector("#captureForm");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#runCapture");
const saveDailyButton = document.querySelector("#saveDaily");
const testExcelButton = document.querySelector("#testExcelBtn");
const historyBody = document.querySelector("#historyBody");
const recordCount = document.querySelector("#recordCount");
const latestDate = document.querySelector("#latestDate");
const larkFields = document.querySelector("#larkFields");
const sourceBadge = document.querySelector("#sourceBadge");
const marketplaceSelect = document.querySelector("#marketplaceSelect");
const marketplaceName = document.querySelector("#marketplaceName");
const domain = document.querySelector("#domain");
const postalCode = document.querySelector("#postalCode");
const marketHint = document.querySelector("#marketHint");
const progressTitle = document.querySelector("#progressTitle");
const progressSub = document.querySelector("#progressSub");
const progressPct = document.querySelector("#progressPct");
const progressFill = document.querySelector("#progressFill");
const logBox = document.querySelector("#logBox");
const resultLinks = document.querySelector("#resultLinks");
const OWNER_KEY = "amazonKeywordTrackerOwnerId";

const MARKETPLACES = {
  US: { name: "Amazon US", domain: "https://www.amazon.com", postal: "10001 / New York", hint: "默认地区：New York, NY。" },
  CA: { name: "Amazon CA", domain: "https://www.amazon.ca", postal: "M5V 2T6 / Toronto", hint: "默认地区：Toronto。" },
  UK: { name: "Amazon UK", domain: "https://www.amazon.co.uk", postal: "SW1A 1AA / London", hint: "默认地区：London。" },
  DE: { name: "Amazon DE", domain: "https://www.amazon.de", postal: "10115 / Berlin", hint: "默认地区：Berlin。" },
  FR: { name: "Amazon FR", domain: "https://www.amazon.fr", postal: "75001 / Paris", hint: "默认地区：Paris。" },
  IT: { name: "Amazon IT", domain: "https://www.amazon.it", postal: "00118 / Rome", hint: "默认地区：Rome。" },
  ES: { name: "Amazon ES", domain: "https://www.amazon.es", postal: "28001 / Madrid", hint: "默认地区：Madrid。" },
  JP: { name: "Amazon JP", domain: "https://www.amazon.co.jp", postal: "100-0001 / Tokyo", hint: "默认地区：Tokyo。" },
  AU: { name: "Amazon AU", domain: "https://www.amazon.com.au", postal: "2000 / Sydney", hint: "默认地区：Sydney。" },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function setBusy(isBusy) {
  runButton.disabled = isBusy;
  saveDailyButton.disabled = isBusy;
  testExcelButton.disabled = isBusy;
}

function activeOutputMode() {
  return new FormData(form).get("outputMode");
}

function getOwnerId() {
  let ownerId = localStorage.getItem(OWNER_KEY);
  if (!ownerId) {
    const randomPart = crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    ownerId = `kwt_${randomPart.replace(/[^A-Za-z0-9_-]/g, "")}`;
    localStorage.setItem(OWNER_KEY, ownerId);
  }
  return ownerId;
}

function captureFormData() {
  const data = new FormData(form);
  data.set("owner_id", getOwnerId());
  return data;
}

function syncDeliveryFields() {
  larkFields.hidden = activeOutputMode() === "excel";
}

function applyMarketplace(code) {
  const item = MARKETPLACES[code] || MARKETPLACES.US;
  marketplaceName.value = item.name;
  domain.value = item.domain;
  postalCode.value = item.postal;
  marketHint.textContent = item.hint;
}

function setProgress(percent, title, sub, log) {
  const pct = Math.max(0, Math.min(100, Number(percent)));
  progressPct.textContent = `${pct}%`;
  progressFill.style.width = `${pct}%`;
  progressTitle.textContent = title;
  progressSub.textContent = sub;
  if (log) {
    logBox.textContent = log;
    logBox.scrollTop = logBox.scrollHeight;
  }
}

async function refreshHistory() {
  const response = await fetch(`/api/history?owner_id=${encodeURIComponent(getOwnerId())}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`历史记录接口不可用：HTTP ${response.status}`);
  const data = await response.json();
  const records = data.records || [];
  historyBody.innerHTML = records
    .map(
      (record) => `
        <tr>
          <td>${escapeHtml(record.date || "")}</td>
          <td>${escapeHtml(record.asin || "")}</td>
          <td>${escapeHtml(record.keyword || "")}</td>
          <td>${escapeHtml(record.organic_position || "")}</td>
          <td>${escapeHtml(record.ad_position || "")}</td>
          <td>${escapeHtml(record.price || "")}</td>
          <td>${escapeHtml(record.estimated_sales || "")}</td>
          <td>${escapeHtml(record.product_rank || "")}</td>
          <td>${escapeHtml(record.rating || "")}</td>
          <td>${escapeHtml(record.review_count || "")}</td>
          <td>${record.product_url ? `<a href="${escapeAttribute(record.product_url)}" target="_blank" rel="noreferrer">打开</a>` : ""}</td>
        </tr>
      `,
    )
    .join("");
  recordCount.textContent = records.length;
  latestDate.textContent = records[0]?.date || "-";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

form.addEventListener("change", (event) => {
  if (event.target.name === "outputMode") syncDeliveryFields();
  if (event.target.id === "marketplaceSelect") applyMarketplace(event.target.value);
});

async function readJsonOrText(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (_error) {
    return { ok: false, error: text.slice(0, 500) || `HTTP ${response.status}` };
  }
}

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollJob(jobId) {
  let gatewayFailures = 0;
  while (true) {
    await wait(1500);
    let data;
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
      data = await readJsonOrText(response);
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      gatewayFailures = 0;
    } catch (error) {
      gatewayFailures += 1;
      setProgress(
        Math.min(95, 10 + gatewayFailures),
        "等待服务恢复",
        "Zeabur 网关暂时没有返回 JSON，正在重试。",
        `读取进度失败 ${gatewayFailures}/20：${error.message}`,
      );
      if (gatewayFailures >= 20) throw new Error("连续读取进度失败，后端服务可能已重启或被 Zeabur 回收。请减少 ASIN/关键词数量后重试。");
      continue;
    }

    const job = data.job || {};
    const logs = (job.logs || []).join("\n");
    if (job.status === "queued") {
      setProgress(job.percent || 1, "等待启动", `共 ${job.total || 0} 条任务。`, logs);
    } else if (job.status === "running") {
      setProgress(job.percent || 20, `抓取中：${job.done || 0}/${job.total || 0}`, "后台正在调用 Sorftime MCP，前台只显示进度。", logs);
    } else if (job.status === "saving") {
      setProgress(job.percent || 88, "保存结果中", "正在生成 Excel 或写入飞书。", logs);
    } else if (job.status === "completed") {
      setProgress(100, "完成", `已处理 ${job.records_count || 0} 条记录。`, logs);
      const links = [];
      if (job.excel) links.push(`<a class="download" href="${escapeAttribute(job.excel)}">下载 Excel</a>`);
      if (job.lark) links.push(`<span class="download">飞书写入 ${job.records_count || 0} 行</span>`);
      if (!links.length) links.push(`<span class="download">已处理 ${job.records_count || 0} 条</span>`);
      resultLinks.innerHTML = links.join("");
      showToast(`已处理：${job.records_count || 0} 条`);
      return job;
    } else if (job.status === "failed") {
      setProgress(job.percent || 12, "失败", job.error || job.lark?.message || "任务失败", logs);
      throw new Error(job.error || job.lark?.message || "任务失败");
    }
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  resultLinks.innerHTML = "";
  setProgress(2, "提交任务中", "正在创建后台任务。", "正在提交任务...");
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: captureFormData(),
    });
    const data = await readJsonOrText(response);
    if (!response.ok || !data.ok) throw new Error(data.error || "任务提交失败");
    const job = data.job || {};
    setProgress(job.percent || 3, "任务已创建", `任务 ID：${job.id || "-"}`, (job.logs || []).join("\n"));
    await pollJob(job.id);
    await refreshHistory();
  } catch (error) {
    setProgress(12, "失败", error.message, error.stack || error.message);
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

testExcelButton.addEventListener("click", async () => {
  setBusy(true);
  setProgress(15, "测试导出中", "正在生成测试 Excel。", "正在请求测试导出...");
  try {
    const response = await fetch("/api/test-excel", { method: "POST" });
    if (!response.ok) throw new Error("测试导出失败");
    const blob = await response.blob();
    downloadBlob(blob, `keyword-rank-test-${new Date().toISOString().slice(0, 10)}.xlsx`);
    setProgress(100, "测试完成", "Excel 导出功能正常。", "测试 Excel 已下载。");
  } catch (error) {
    setProgress(12, "测试失败", error.message, error.stack || error.message);
  } finally {
    setBusy(false);
  }
});

saveDailyButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const response = await fetch("/api/daily", {
      method: "POST",
      body: captureFormData(),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "保存失败");
    showToast("每日任务已保存");
    setProgress(100, "每日任务已保存", "本地服务保持运行时会按时抓取。", "每日任务配置已保存。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

document.querySelector("#refreshHistory").addEventListener("click", refreshHistory);

async function boot() {
  applyMarketplace(marketplaceSelect.value);
  syncDeliveryFields();
  try {
    const health = await fetch("/api/health", { cache: "no-store" });
    sourceBadge.textContent = health.ok
      ? "服务已连接，输出自然位、广告位、价格、销量、排名、评分和评价数。"
      : "服务启动异常，请检查 Zeabur Runtime Logs。";
  } catch (_error) {
    sourceBadge.textContent = "后端服务暂不可用，请检查 Zeabur Runtime Logs。";
  }
  try {
    await refreshHistory();
  } catch (_error) {
    historyBody.innerHTML = "";
  }
}

boot();
