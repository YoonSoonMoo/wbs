// ===== API Helper =====
async function _handleResponse(res) {
    if (res.status === 401) {
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    if (res.status === 403) {
        showToast('권한이 부족합니다.', 'error');
        throw new Error('Forbidden');
    }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

const API = {
    async get(url) {
        const res = await fetch(url);
        return _handleResponse(res);
    },
    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return _handleResponse(res);
    },
    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return _handleResponse(res);
    },
    async patch(url, data) {
        const res = await fetch(url, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return _handleResponse(res);
    },
    async delete(url) {
        const res = await fetch(url, { method: 'DELETE' });
        return _handleResponse(res);
    },
};

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}

// ===== Debounce =====
function debounce(fn, delay) {
    if (!delay) delay = 300;
    var timer;
    return function() {
        var args = arguments;
        var ctx = this;
        clearTimeout(timer);
        timer = setTimeout(function() { fn.apply(ctx, args); }, delay);
    };
}
