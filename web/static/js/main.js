/**
 * Crypto Trading Bot Dashboard - JavaScript
 * Real-time updates via WebSocket
 */

// =============================================================================
// INITIALIZATION
// =============================================================================

const socket = io();
let isConnected = false;
let botRunning = false;
let paperMode = true;

// Default coins
const defaultCoins = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'MATIC/USDT'
];

let activeCoins = [...defaultCoins];

// =============================================================================
// DOM ELEMENTS
// =============================================================================

const elements = {
    // Status
    balance: document.getElementById('balance'),
    totalPnl: document.getElementById('total-pnl'),
    openPositions: document.getElementById('open-positions'),
    botStatus: document.getElementById('bot-status'),
    connectionStatus: document.getElementById('connection-status'),
    lastUpdate: document.getElementById('last-update'),

    // Controls
    startBtn: document.getElementById('start-btn'),
    stopBtn: document.getElementById('stop-btn'),
    modeBtn: document.getElementById('mode-btn'),
    saveTriggersBtn: document.getElementById('save-triggers'),

    // Triggers - Buy
    rsiBuySlider: document.getElementById('rsi-buy-slider'),
    rsiBuy: document.getElementById('rsi-buy'),
    dipSlider: document.getElementById('dip-slider'),
    dipPercent: document.getElementById('dip-percent'),
    volumeSlider: document.getElementById('volume-slider'),
    volumeSpike: document.getElementById('volume-spike'),
    requireAllBuy: document.getElementById('require-all-buy'),

    // Triggers - Sell
    rsiSellSlider: document.getElementById('rsi-sell-slider'),
    rsiSell: document.getElementById('rsi-sell'),
    riseSlider: document.getElementById('rise-slider'),
    risePercent: document.getElementById('rise-percent'),
    stoplossSlider: document.getElementById('stoploss-slider'),
    stopLoss: document.getElementById('stop-loss'),

    // Tables and lists
    pricesBody: document.getElementById('prices-body'),
    openTrades: document.getElementById('open-trades'),
    closedTrades: document.getElementById('closed-trades'),
    activityLog: document.getElementById('activity-log'),
    coinCheckboxes: document.getElementById('coin-checkboxes'),
    customCoin: document.getElementById('custom-coin'),
    addCoinBtn: document.getElementById('add-coin-btn'),
    clearLogBtn: document.getElementById('clear-log'),

    // Wallet
    walletBtn: document.getElementById('wallet-btn'),
    walletModal: document.getElementById('wallet-modal'),
    closeModal: document.querySelector('.close-modal'),
    depositInput: document.getElementById('deposit-amount'),
    depositBtn: document.getElementById('deposit-btn'),
    withdrawInput: document.getElementById('withdraw-amount'),
    withdrawBtn: document.getElementById('withdraw-btn'),
    resetWalletBtn: document.getElementById('reset-wallet-btn'),
};

// =============================================================================
// SOCKET EVENTS
// =============================================================================

socket.on('connect', () => {
    isConnected = true;
    updateConnectionStatus(true);
    log('Connected to server', 'success');
    socket.emit('get_update');
});

socket.on('disconnect', () => {
    isConnected = false;
    updateConnectionStatus(false);
    log('Disconnected from server', 'error');
});

socket.on('status', (data) => {
    if (data.connected) {
        log('WebSocket connection established', 'info');
    }
});

socket.on('update', (data) => {
    updateDashboard(data);
});

socket.on('trade', (data) => {
    const emoji = data.signal === 'buy' ? '📈' : '📉';
    log(`${emoji} ${data.signal.toUpperCase()} ${data.symbol} @ $${formatPrice(data.price)} - ${data.reasons.join(', ')}`, 'trade');
    fetchTrades();
});

// =============================================================================
// EVENT LISTENERS
// =============================================================================

// Bot controls
elements.startBtn.addEventListener('click', startBot);
elements.stopBtn.addEventListener('click', stopBot);
elements.modeBtn.addEventListener('click', toggleMode);
elements.saveTriggersBtn.addEventListener('click', saveTriggers);
elements.clearLogBtn.addEventListener('click', clearLog);

// Slider sync
syncSlider(elements.rsiBuySlider, elements.rsiBuy);
syncSlider(elements.dipSlider, elements.dipPercent);
syncSlider(elements.volumeSlider, elements.volumeSpike);
syncSlider(elements.rsiSellSlider, elements.rsiSell);
syncSlider(elements.riseSlider, elements.risePercent);
syncSlider(elements.stoplossSlider, elements.stopLoss);

// Coin management
elements.addCoinBtn.addEventListener('click', addCustomCoin);
elements.customCoin.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') addCustomCoin();
});

// Wallet Events
elements.walletBtn.addEventListener('click', () => {
    elements.walletModal.style.display = 'block';
});

elements.closeModal.addEventListener('click', () => {
    elements.walletModal.style.display = 'none';
});

window.addEventListener('click', (event) => {
    if (event.target == elements.walletModal) {
        elements.walletModal.style.display = 'none';
    }
});

elements.depositBtn.addEventListener('click', depositFunds);
elements.withdrawBtn.addEventListener('click', withdrawFunds);
elements.resetWalletBtn.addEventListener('click', resetWallet);

// Tab switching - Dashboard Panels
document.querySelectorAll('.trades-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab, 'trades'));
});

// Tab switching - Dashboard Panels (Trades only now)
document.querySelectorAll('.trades-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab, 'trades'));
});

// Initial Load
fetchTop100();
// Refresh Top 100 every 60 seconds
setInterval(fetchTop100, 60000);


// =============================================================================
// FUNCTIONS
// =============================================================================

function syncSlider(slider, input) {
    slider.addEventListener('input', () => {
        input.value = slider.value;
    });
    input.addEventListener('input', () => {
        slider.value = input.value;
    });
}

function updateConnectionStatus(connected) {
    const el = elements.connectionStatus;
    if (connected) {
        el.textContent = '● Connected';
        el.className = 'connected';
    } else {
        el.textContent = '● Disconnected';
        el.className = 'disconnected';
    }
}

function updateDashboard(data) {
    // Balance
    const balance = data.balance?.USDT || 0;
    elements.balance.textContent = `$${formatNumber(balance)}`;

    // Total P/L
    const pnl = data.total_pnl || 0;
    elements.totalPnl.textContent = `$${formatNumber(pnl)}`;
    elements.totalPnl.className = `stat-value ${pnl >= 0 ? 'positive' : 'negative'}`;

    // Open positions
    const positions = data.positions || [];
    elements.openPositions.textContent = positions.length;

    // Bot status
    botRunning = data.running;
    updateBotStatus(data.running);

    // Paper mode
    paperMode = data.paper_mode;
    updateModeButton(data.paper_mode);

    // Prices
    if (data.prices) {
        updatePricesTable(data.prices);
    }

    // Last update
    if (data.last_update) {
        const time = new Date(data.last_update).toLocaleTimeString();
        elements.lastUpdate.textContent = time;
    }
}

function updateBotStatus(running) {
    elements.botStatus.textContent = running ? 'Running' : 'Stopped';
    elements.botStatus.className = `stat-value ${running ? 'status-running' : 'status-stopped'}`;
    elements.startBtn.disabled = running;
    elements.stopBtn.disabled = !running;
}

function updateModeButton(paper) {
    elements.modeBtn.textContent = paper ? 'PAPER' : 'LIVE';
    elements.modeBtn.className = `mode-btn ${paper ? 'paper' : 'live'}`;
}

function updatePricesTable(prices) {
    let html = '';

    prices.forEach(coin => {
        const symbol = coin.symbol.split('/')[0];
        const changeClass = coin.change_24h >= 0 ? 'change-positive' : 'change-negative';
        const changeSign = coin.change_24h >= 0 ? '+' : '';

        let rsiClass = 'rsi-neutral';
        if (coin.rsi < 30) rsiClass = 'rsi-oversold';
        else if (coin.rsi > 70) rsiClass = 'rsi-overbought';

        let signal = 'HOLD';
        let signalClass = 'signal-hold';
        if (coin.rsi < 30 || coin.dip_percent > 5) {
            signal = 'BUY';
            signalClass = 'signal-buy';
        } else if (coin.rsi > 70) {
            signal = 'SELL';
            signalClass = 'signal-sell';
        }

        const isSelected = (typeof currentChartSymbol !== 'undefined' && currentChartSymbol === coin.symbol) ? 'selected' : '';

        html += `
            <tr data-symbol="${coin.symbol}" class="${isSelected}">
                <td>
                    <span class="coin-symbol">
                        <span class="coin-icon">${symbol.charAt(0)}</span>
                        ${symbol}
                    </span>
                </td>
                <td class="price-value">$${formatPrice(coin.price)}</td>
                <td class="${changeClass}">${changeSign}${coin.change_24h?.toFixed(2) || 0}%</td>
                <td><span class="rsi-value ${rsiClass}">${coin.rsi?.toFixed(1) || 'N/A'}</span></td>
                <td>${coin.dip_percent?.toFixed(1) || 0}%</td>
                <td>${coin.volume_spike?.toFixed(1) || 1}x</td>
                <td><span class="signal-badge ${signalClass}">${signal}</span></td>
            </tr>
        `;
    });

    elements.pricesBody.innerHTML = html || '<tr><td colspan="7" class="loading">No data</td></tr>';
}

async function startBot() {
    try {
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            log('Bot started', 'success');
            updateBotStatus(true);
        }
    } catch (error) {
        log(`Failed to start bot: ${error.message}`, 'error');
    }
}

async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            log('Bot stopped', 'info');
            updateBotStatus(false);
        }
    } catch (error) {
        log(`Failed to stop bot: ${error.message}`, 'error');
    }
}

async function toggleMode() {
    const newPaperMode = !paperMode;

    if (!newPaperMode) {
        if (!confirm('⚠️ WARNING: Switching to LIVE mode will execute REAL trades with REAL money. Are you sure?')) {
            return;
        }
    }

    try {
        const response = await fetch('/api/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paper_mode: newPaperMode })
        });
        const data = await response.json();
        if (data.success) {
            paperMode = data.paper_mode;
            updateModeButton(paperMode);
            log(`Mode switched to ${paperMode ? 'PAPER' : 'LIVE'}`, paperMode ? 'info' : 'error');
        }
    } catch (error) {
        log(`Failed to switch mode: ${error.message}`, 'error');
    }
}

async function saveTriggers() {
    const triggers = {
        buy: {
            rsi_below: parseFloat(elements.rsiBuy.value),
            dip_percent: parseFloat(elements.dipPercent.value),
            volume_spike: parseFloat(elements.volumeSpike.value),
            enabled: true,
            require_all: elements.requireAllBuy.checked,
        },
        sell: {
            rsi_above: parseFloat(elements.rsiSell.value),
            rise_percent: parseFloat(elements.risePercent.value),
            stop_loss: parseFloat(elements.stopLoss.value),
            take_profit: parseFloat(elements.risePercent.value),
            enabled: true,
        }
    };

    try {
        const response = await fetch('/api/triggers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(triggers)
        });
        const data = await response.json();
        if (data.success) {
            log('Triggers saved successfully', 'success');
        }
    } catch (error) {
        log(`Failed to save triggers: ${error.message}`, 'error');
    }
}

async function fetchTrades() {
    try {
        const response = await fetch('/api/trades');
        const data = await response.json();

        // Update open trades
        if (data.open && data.open.length > 0) {
            elements.openTrades.innerHTML = data.open.map(renderTradeCard).join('');
        } else {
            elements.openTrades.innerHTML = '<p class="no-trades">No open positions</p>';
        }

        // Update closed trades
        if (data.closed && data.closed.length > 0) {
            elements.closedTrades.innerHTML = data.closed.slice(-20).reverse().map(renderTradeCard).join('');
        } else {
            elements.closedTrades.innerHTML = '<p class="no-trades">No closed trades yet</p>';
        }
    } catch (error) {
        console.error('Failed to fetch trades:', error);
    }
}

function renderTradeCard(trade) {
    const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
    const pnlSign = trade.pnl >= 0 ? '+' : '';

    return `
        <div class="trade-card">
            <div class="trade-header">
                <span class="trade-symbol">${trade.symbol}</span>
                <span class="trade-side ${trade.side}">${trade.side.toUpperCase()}</span>
            </div>
            <div class="trade-details">
                <span>Entry: $${formatPrice(trade.entry_price)}</span>
                <span>Qty: ${trade.quantity.toFixed(6)}</span>
                ${trade.exit_price ? `<span>Exit: $${formatPrice(trade.exit_price)}</span>` : ''}
                ${trade.entry_time ? `<span>${new Date(trade.entry_time).toLocaleString()}</span>` : ''}
            </div>
            ${trade.status === 'closed' ? `
                <div class="trade-pnl ${pnlClass}">
                    ${pnlSign}$${formatNumber(trade.pnl)} (${pnlSign}${trade.pnl_percent.toFixed(2)}%)
                </div>
            ` : ''}
        </div>
    `;
}

function switchTab(tab, group = 'trades') {
    let container;
    if (group === 'trades') {
        container = elements.openTrades.parentElement;
    }

    if (!container) return;

    // Update buttons
    container.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Update content
    if (group === 'trades') {
        document.querySelectorAll('.trades-list').forEach(list => {
            list.classList.toggle('active', list.id === `${tab}-trades`);
        });
    }
}

function addCustomCoin() {
    const coin = elements.customCoin.value.trim().toUpperCase();
    if (!coin) return;

    // Validate format
    if (!coin.includes('/')) {
        alert('Please enter coin in format: COIN/USDT (e.g., LINK/USDT)');
        return;
    }

    if (!activeCoins.includes(coin)) {
        activeCoins.push(coin);
        updateCoinList();
        elements.customCoin.value = '';
        log(`Added ${coin} to watchlist`, 'info');
    }
}

function updateCoinList() {
    elements.coinCheckboxes.innerHTML = activeCoins.map(coin => {
        const symbol = coin.split('/')[0];
        return `
            <label class="coin-chip active" data-coin="${coin}">
                <input type="checkbox" checked style="display:none">
                ${symbol}
                <span class="remove-coin" onclick="removeCoin('${coin}')">×</span>
            </label>
        `;
    }).join('');
}

function removeCoin(coin) {
    activeCoins = activeCoins.filter(c => c !== coin);
    updateCoinList();
    log(`Removed ${coin} from watchlist`, 'info');
}

function log(message, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-msg">${message}</span>
    `;
    elements.activityLog.insertBefore(entry, elements.activityLog.firstChild);

    // Keep only last 50 entries
    while (elements.activityLog.children.length > 50) {
        elements.activityLog.removeChild(elements.activityLog.lastChild);
    }
}

function clearLog() {
    elements.activityLog.innerHTML = '';
    log('Log cleared', 'info');
}

function formatPrice(price) {
    if (!price) return '0.00';
    if (price >= 1000) return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(2);
    if (price >= 0.01) return price.toFixed(4);
    return price.toFixed(6);
}

function formatNumber(num) {
    if (!num) return '0.00';
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// =============================================================================
// INITIALIZE
// =============================================================================

// Chart variables
let priceChart = null;
let currentChartSymbol = null;
let currentTimeframe = '1h';

document.addEventListener('DOMContentLoaded', () => {
    updateCoinList();

    // Initial data fetch
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            paperMode = data.paper_mode;
            updateModeButton(paperMode);
            updateBotStatus(data.running);

            // Update triggers from server
            if (data.triggers) {
                const buy = data.triggers.buy || {};
                const sell = data.triggers.sell || {};

                elements.rsiBuy.value = buy.rsi_below || 30;
                elements.rsiBuySlider.value = buy.rsi_below || 30;
                elements.dipPercent.value = buy.dip_percent || 5;
                elements.dipSlider.value = buy.dip_percent || 5;
                elements.volumeSpike.value = buy.volume_spike || 1.5;
                elements.volumeSlider.value = buy.volume_spike || 1.5;
                elements.requireAllBuy.checked = buy.require_all || false;

                elements.rsiSell.value = sell.rsi_above || 70;
                elements.rsiSellSlider.value = sell.rsi_above || 70;
                elements.risePercent.value = sell.rise_percent || 10;
                elements.riseSlider.value = sell.rise_percent || 10;
                elements.stopLoss.value = sell.stop_loss || 5;
                elements.stoplossSlider.value = sell.stop_loss || 5;
            }
        })
        .catch(err => console.error('Failed to fetch initial status:', err));

    fetchTrades();

    // Periodic refresh
    setInterval(() => {
        if (isConnected) {
            socket.emit('get_update');
        }
    }, 10000);

    // Chart controls
    setupChartControls();
});

// =============================================================================
// CHART FUNCTIONS
// =============================================================================

function setupChartControls() {
    // Close chart button
    const closeBtn = document.getElementById('close-chart');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideChart);
    }

    // Overlay Buy/Sell buttons
    const buyBtn = document.getElementById('chart-btn-buy');
    const sellBtn = document.getElementById('chart-btn-sell');

    if (buyBtn) {
        buyBtn.addEventListener('click', () => manualTrade('buy'));
    }
    if (sellBtn) {
        sellBtn.addEventListener('click', () => manualTrade('sell'));
    }

    // Click on price table rows to show chart
    document.getElementById('prices-body').addEventListener('click', (e) => {
        const row = e.target.closest('tr');
        if (row && row.dataset.symbol) {
            showChart(row.dataset.symbol);
        }
    });

    // Make overlay buttons draggable
    const overlay = document.querySelector('.chart-overlay-controls');
    if (overlay) {
        makeElementDraggable(overlay);
    }
}

function makeElementDraggable(elmnt) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    elmnt.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
        e = e || window.event;
        // Don't prevent default on buttons so they can be clicked
        if (e.target.tagName !== 'BUTTON') {
            e.preventDefault();
        }
        // But we want to drag even if clicking button? No, that conflicts.
        // Let's drag only when clicking the container or non-button space
        if (e.target.tagName === 'BUTTON') return;

        // get the mouse cursor position at startup:
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        // call a function whenever the cursor moves:
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        // calculate the new cursor position:
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        // set the element's new position:
        elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
        elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        // stop moving when mouse button is released:
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

function showChart(symbol) {
    currentChartSymbol = symbol;
    const chartPanel = document.getElementById('chart-panel');
    const chartTitle = document.getElementById('chart-title');

    chartPanel.style.display = 'block';
    chartTitle.textContent = `${symbol} Price Chart`;

    // Highlight selected row
    document.querySelectorAll('#prices-body tr').forEach(row => {
        row.classList.remove('selected');
        if (row.dataset.symbol === symbol) {
            row.classList.add('selected');
        }
    });

    loadChart(symbol, currentTimeframe);
    log(`Viewing chart for ${symbol}`, 'info');

    // Scroll chart into view
    setTimeout(() => {
        chartPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function hideChart() {
    const chartPanel = document.getElementById('chart-panel');
    chartPanel.style.display = 'none';
    currentChartSymbol = null;

    // Remove selection
    document.querySelectorAll('#prices-body tr').forEach(row => {
        row.classList.remove('selected');
    });
}

async function loadChart(symbol, timeframe) {
    try {
        // Fetch our indicator data
        const urlSymbol = symbol.replace('/', '-');
        const response = await fetch(`/api/chart/${urlSymbol}?timeframe=${timeframe}&limit=100`);
        const data = await response.json();

        // Update indicators regardless of chart source
        updateChartIndicators(data);

        // Create TradingView widget
        renderTradingViewChart(symbol);

    } catch (error) {
        console.error('Failed to load chart data:', error);
        // Still try to render TradingView even if our API fails
        renderTradingViewChart(symbol);
    }
}

function renderTradingViewChart(symbol) {
    const container = document.getElementById('tradingview-widget');

    // Clear previous widget
    container.innerHTML = '';

    // Convert symbol format: "BTC/USDT" -> "MEXC:BTCUSDT"
    const tvSymbol = 'MEXC:' + symbol.replace('/', '');

    // Create TradingView Advanced Chart widget
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.innerHTML = JSON.stringify({
        "autosize": true,
        "symbol": tvSymbol,
        "interval": "60",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "backgroundColor": "rgba(17, 24, 39, 1)",
        "gridColor": "rgba(255, 255, 255, 0.06)",
        "hide_top_toolbar": false,
        "hide_side_toolbar": false,
        "hide_legend": false,
        "allow_symbol_change": true,
        "save_image": false,
        "calendar": false,
        "hide_volume": false,
        "support_host": "https://www.tradingview.com",
        "studies": [
            "RSI@tv-basicstudies"
        ]
    });

    // Wrap in TradingView widget container div
    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container';
    widgetContainer.style.height = '100%';
    widgetContainer.style.width = '100%';

    const widgetInner = document.createElement('div');
    widgetInner.className = 'tradingview-widget-container__widget';
    widgetInner.style.height = '100%';
    widgetInner.style.width = '100%';

    widgetContainer.appendChild(widgetInner);
    widgetContainer.appendChild(script);
    container.appendChild(widgetContainer);
}

function updateChartIndicators(data) {
    const rsiEl = document.getElementById('chart-rsi');
    const highEl = document.getElementById('chart-high');
    const lowEl = document.getElementById('chart-low');
    const dipEl = document.getElementById('chart-dip');

    if (rsiEl) {
        rsiEl.textContent = data.rsi?.toFixed(1) || '--';
        rsiEl.style.color = data.rsi < 30 ? '#10b981' : data.rsi > 70 ? '#ef4444' : '#f9fafb';
    }
    if (highEl) {
        highEl.textContent = '$' + formatPrice(data.high_24h);
    }
    if (lowEl) {
        lowEl.textContent = '$' + formatPrice(data.low_24h);
    }
    if (dipEl) {
        dipEl.textContent = (data.dip_percent?.toFixed(1) || 0) + '%';
    }
}

function manualTrade(side) {
    if (!currentChartSymbol) return;

    const action = side.toUpperCase();
    const emoji = side === 'buy' ? '🟢' : '🔴';

    if (confirm(`Confirm MANUAL ${action} order for ${currentChartSymbol}?`)) {
        log(`${emoji} Manual ${action} order executed for ${currentChartSymbol}`, side === 'buy' ? 'success' : 'error');
        // Future: fetch('/api/trade', { method: 'POST', body: JSON.stringify({ symbol: currentChartSymbol, side: side }) });
    }
}

// Wallet Functions
async function depositFunds() {
    const amount = parseFloat(elements.depositInput.value);
    if (!amount || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }

    try {
        const response = await fetch('/api/wallet/deposit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount })
        });
        const data = await response.json();

        if (data.success) {
            log(`Deposited $${amount}`, 'success');
            elements.depositInput.value = '';
            elements.walletModal.style.display = 'none';
        } else {
            alert('Deposit failed: ' + data.error);
        }
    } catch (error) {
        console.error('Error depositing funds:', error);
    }
}

async function withdrawFunds() {
    const amount = parseFloat(elements.withdrawInput.value);
    if (!amount || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }

    try {
        const response = await fetch('/api/wallet/withdraw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount })
        });
        const data = await response.json();

        if (data.success) {
            log(`Withdrew $${amount}`, 'success');
            elements.withdrawInput.value = '';
            elements.walletModal.style.display = 'none';
        } else {
            alert('Withdrawal failed: ' + data.error);
        }
    } catch (error) {
        console.error('Error withdrawing funds:', error);
    }
}

async function fetchTop100() {
    const tbody = document.getElementById('top100-body');
    if (!tbody) return;

    try {
        const response = await fetch('/api/market/top100');
        const data = await response.json();

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No data available</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(coin => {
            const changeClass = coin.change_24h >= 0 ? 'positive' : 'negative';
            const changeSign = coin.change_24h >= 0 ? '+' : '';

            return `
                <tr>
                    <td style="color: var(--text-secondary)">#${coin.rank}</td>
                    <td>
                        <div class="coin-symbol">
                            <img src="${coin.image}" alt="" style="width: 20px; height: 20px; border-radius: 50%;">
                            <span>${coin.name}</span>
                            <span style="color: var(--text-secondary); font-size: 0.8rem;">${coin.symbol}</span>
                        </div>
                    </td>
                    <td class="price-value">$${formatPrice(coin.price)}</td>
                    <td class="${changeClass}">${changeSign}${coin.change_24h.toFixed(2)}%</td>
                    <td>$${formatNumber(coin.market_cap)}</td>
                    <td>$${formatNumber(coin.volume)}</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error('Error fetching Top 100:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="error">Failed to load data</td></tr>';
    }
}

async function resetWallet() {
    if (!confirm('Are you sure you want to reset your paper wallet to $10,000? All trade history will be preserved.')) {
        return;
    }

    try {
        const response = await fetch('/api/wallet/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: 10000 })
        });
        const data = await response.json();

        if (data.success) {
            log('Wallet reset to default', 'warning');
            elements.walletModal.style.display = 'none';
        }
    } catch (error) {
        console.error('Error resetting wallet:', error);
    }
}

// Make removeCoin available globally
window.removeCoin = removeCoin;
