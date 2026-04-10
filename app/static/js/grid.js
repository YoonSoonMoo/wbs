// ===== WBS Grid (template 호환) =====
var COLUMNS = ['category','task_name','subtask','detail','assignee','plan_start','plan_end','actual_start','actual_end','effort','progress','status'];
var data = [];
var contextRowIdx = -1;
var sortCol = null;
var sortDir = 'asc';

// ===== Data Loading =====
async function loadItems() {
    try {
        var items = await API.get('/api/wbs/' + PROJECT_ID + '/items');
        data = items.map(function(item) {
            return {
                _id: item.id,
                category: item.category || '',
                task_name: item.task_name || '',
                subtask: item.subtask || '',
                detail: item.detail || '',
                assignee: item.assignee || '',
                plan_start: item.plan_start || '',
                plan_end: item.plan_end || '',
                actual_start: item.actual_start || '',
                actual_end: item.actual_end || '',
                effort: item.effort ? String(item.effort) : '',
                progress: item.progress != null ? String(item.progress) : '0',
                status: item.status || ''
            };
        });
        renderGrid();
    } catch (e) {
        showToast('데이터를 불러올 수 없습니다.', 'error');
    }
}

// ===== Rendering =====
function esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderGrid() {
    var tbody = document.getElementById('wbsBody');
    var sv = (document.getElementById('searchInput').value || '').toLowerCase();
    var fs = document.getElementById('filterStatus').value;
    var fa = document.getElementById('filterAssignee').value;
    var filtered = [];

    for (var i = 0; i < data.length; i++) {
        var r = data[i]; r._idx = i;
        if (sv) {
            var found = false;
            for (var k in r) { if (String(r[k]).toLowerCase().indexOf(sv) >= 0) { found = true; break; } }
            if (!found) continue;
        }
        if (fs) {
            var p = parseFloat(r.progress) || 0;
            if (fs === 'done' && p < 100) continue;
            if (fs === 'ing' && (p <= 0 || p >= 100)) continue;
            if (fs === 'not' && p > 0) continue;
        }
        if (fa && r.assignee !== fa) continue;
        filtered.push(r);
    }

    if (sortCol) {
        filtered.sort(function(a, b) {
            var va = a[sortCol] || '', vb = b[sortCol] || '';
            if (sortCol === 'progress' || sortCol === 'effort') { va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; }
            return sortDir === 'asc' ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
        });
    }

    var canEdit = (typeof USER_ROLE !== 'undefined' && USER_ROLE !== 'viewer');
    var ceAttr = canEdit ? ' contenteditable="true"' : '';
    var editClass = canEdit ? 'editable' : '';

    var h = '';
    for (var i = 0; i < filtered.length; i++) {
        var row = filtered[i];
        var p = parseFloat(row.progress) || 0;
        var pColor = p >= 100 ? 'var(--accent-green)' : p >= 50 ? 'var(--accent-blue)' : p > 0 ? 'var(--accent-yellow)' : '#d1d5db';
        h += '<tr data-idx="' + row._idx + '"' + (canEdit ? ' oncontextmenu="showContext(event,' + row._idx + ')"' : '') + '>';
        h += '<td class="row-num">' + (i + 1) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="category">' + esc(row.category) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="task_name">' + esc(row.task_name) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="subtask">' + esc(row.subtask) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="detail">' + esc(row.detail) + '</td>';
        h += '<td class="' + editClass + ' cell-center"' + ceAttr + ' data-col="assignee">' + esc(row.assignee) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="plan_start">' + esc(row.plan_start) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="plan_end">' + esc(row.plan_end) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="actual_start">' + esc(row.actual_start) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="actual_end">' + esc(row.actual_end) + '</td>';
        h += '<td class="' + editClass + ' cell-num"' + ceAttr + ' data-col="effort">' + esc(row.effort) + '</td>';
        h += '<td class="cell-progress"><div class="progress-bar-cell"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:' + p + '%;background:' + pColor + '"></div></div><span class="progress-val">' + p + '%</span></div></td>';
        h += '<td class="' + editClass + ' cell-status"' + ceAttr + ' data-col="status">' + esc(row.status) + '</td>';
        h += '</tr>';
    }
    tbody.innerHTML = h;
    updateStats(filtered);
    updateAlerts();
    updateAssigneeFilter();
    document.getElementById('footerRows').textContent = data.length;
}

// ===== Stats =====
function updateStats(f) {
    document.getElementById('statTotal').textContent = f.length;
    var d = 0, p = 0, dl = 0;
    for (var i = 0; i < f.length; i++) {
        var pr = parseFloat(f[i].progress) || 0;
        if (pr >= 100) d++;
        else if (pr > 0) p++;
        var s = (f[i].status || '').toLowerCase();
        if (s.indexOf('지연') >= 0) dl++;
    }
    document.getElementById('statDone').textContent = d;
    document.getElementById('statProgress').textContent = p;
    document.getElementById('statDelayed').textContent = dl;
}

// ===== Alerts =====
function updateAlerts() {
    var today = new Date();
    var delayed = [];
    for (var i = 0; i < data.length; i++) {
        var r = data[i];
        if ((parseFloat(r.progress) || 0) >= 100 || !r.plan_end) continue;
        var ed;
        // YYYY-MM-DD format
        if (r.plan_end.indexOf('-') >= 0) {
            ed = new Date(r.plan_end);
        }
        // MM/DD format
        else if (r.plan_end.indexOf('/') >= 0) {
            var pts = r.plan_end.split('/');
            if (pts.length !== 2) continue;
            var m = parseInt(pts[0]) - 1, d = parseInt(pts[1]);
            if (isNaN(m) || isNaN(d)) continue;
            ed = new Date(today.getFullYear(), m, d);
        } else continue;

        if (ed < today) {
            delayed.push({ detail: r.detail || r.subtask, days: Math.ceil((today - ed) / 864e5) });
        }
    }
    var sec = document.getElementById('alertSection');
    var con = document.getElementById('alertItems');
    document.getElementById('alertCount').textContent = delayed.length;
    if (!delayed.length) {
        sec.className = 'alert-section no-alerts';
        con.innerHTML = '<span class="alert-empty">지연된 업무가 없습니다 ✓</span>';
    } else {
        sec.className = 'alert-section';
        var ch = '';
        for (var i = 0; i < delayed.length; i++) {
            ch += '<span class="alert-chip"><span class="chip-task">' + esc(delayed[i].detail) + '</span><span class="chip-days">+' + delayed[i].days + '일</span></span>';
        }
        con.innerHTML = ch;
    }
}

// ===== Assignee Filter =====
function updateAssigneeFilter() {
    var sel = document.getElementById('filterAssignee');
    var cur = sel.value;
    var m = {};
    for (var i = 0; i < data.length; i++) { if (data[i].assignee) m[data[i].assignee] = true; }
    var a = Object.keys(m).sort();
    sel.innerHTML = '<option value="">전체 담당자</option>';
    for (var i = 0; i < a.length; i++) {
        sel.innerHTML += '<option value="' + a[i] + '"' + (a[i] === cur ? ' selected' : '') + '>' + a[i] + '</option>';
    }
}

function filterGrid() { renderGrid(); }

// ===== Cell Editing =====
var saveTimer = null;

document.addEventListener('focusout', function(e) {
    if (!e.target.classList.contains('editable')) return;
    var tr = e.target.closest('tr'); if (!tr) return;
    var idx = parseInt(tr.dataset.idx), col = e.target.dataset.col;
    if (data[idx]) {
        var newVal = e.target.textContent.trim();
        if (data[idx][col] !== newVal) {
            data[idx][col] = newVal;
            // Save to API
            saveField(data[idx]._id, col, newVal);
            if (col === 'progress') renderGrid();
        }
    }
});

document.addEventListener('keydown', function(e) {
    if (!e.target.classList.contains('editable')) return;
    if (e.key === 'Tab') {
        e.preventDefault();
        var n = e.shiftKey ? e.target.previousElementSibling : e.target.nextElementSibling;
        if (n && n.classList.contains('editable')) { n.focus(); window.getSelection().selectAllChildren(n); }
    }
    if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
});

// ===== Paste in cell =====
document.addEventListener('paste', function(e) {
    var a = document.activeElement;
    if (a && a.classList.contains('editable')) {
        var t = (e.clipboardData || window.clipboardData).getData('text');
        if (t.indexOf('\t') >= 0 || (t.indexOf('\n') >= 0 && t.trim().split('\n').length > 1)) {
            e.preventDefault();
            pasteIntoGrid(t, a);
        }
    }
});

function pasteIntoGrid(text, cell) {
    var rows = text.split('\n');
    var rr = [];
    for (var i = 0; i < rows.length; i++) { if (rows[i].trim()) rr.push(rows[i]); }
    var tr = cell.closest('tr');
    var si = parseInt(tr.dataset.idx);
    var co = COLUMNS;
    var sci = co.indexOf(cell.dataset.col); if (sci < 0) sci = 0;
    for (var i = 0; i < rr.length; i++) {
        var cells = rr[i].split('\t');
        var di = si + i;
        while (di >= data.length) {
            data.push({ _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' });
        }
        for (var j = 0; j < cells.length; j++) {
            var ci = sci + j;
            if (ci < co.length) data[di][co[ci]] = cells[j].trim();
        }
    }
    saveBatch();
    renderGrid();
}

// ===== Sort =====
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('th.sortable').forEach(function(th) {
        th.addEventListener('click', function() {
            var c = th.dataset.col;
            if (sortCol === c) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            else { sortCol = c; sortDir = 'asc'; }
            renderGrid();
        });
    });
});

// ===== Row Operations =====
function addRow() {
    var newItem = { _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' };
    data.push(newItem);
    // Save to API
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '' }).then(function(item) {
        newItem._id = item.id;
        renderGrid();
        var tb = document.getElementById('wbsBody');
        if (tb.lastElementChild) tb.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }).catch(function() {
        showToast('행 추가 실패', 'error');
    });
    renderGrid();
}

function newRow() {
    return { _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' };
}

function showContext(e, idx) {
    e.preventDefault();
    if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'viewer') return;
    contextRowIdx = idx;
    var m = document.getElementById('contextMenu');
    m.style.left = e.clientX + 'px';
    m.style.top = e.clientY + 'px';
    m.classList.add('show');
}
document.addEventListener('click', function() { document.getElementById('contextMenu').classList.remove('show'); });

function insertRowAbove() {
    var nr = newRow();
    data.splice(contextRowIdx, 0, nr);
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '', sort_order: contextRowIdx }).then(function(item) {
        nr._id = item.id;
    });
    renderGrid();
}

function insertRowBelow() {
    var nr = newRow();
    data.splice(contextRowIdx + 1, 0, nr);
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '', sort_order: contextRowIdx + 1 }).then(function(item) {
        nr._id = item.id;
    });
    renderGrid();
}

function duplicateRow() {
    var o = {};
    var src = data[contextRowIdx];
    for (var k in src) o[k] = src[k];
    o._id = null;
    data.splice(contextRowIdx + 1, 0, o);
    var apiData = {};
    COLUMNS.forEach(function(c) { apiData[c] = o[c] || ''; });
    apiData.effort = parseFloat(apiData.effort) || 0;
    apiData.progress = parseInt(apiData.progress) || 0;
    API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
        o._id = item.id;
    });
    renderGrid();
}

function deleteRow() {
    var item = data[contextRowIdx];
    if (item._id) {
        API.delete('/api/wbs/items/' + item._id).catch(function() {
            showToast('삭제 실패', 'error');
        });
    }
    data.splice(contextRowIdx, 1);
    renderGrid();
}

function confirmClear() {
    if (!confirm('모든 데이터를 초기화하시겠습니까?')) return;
    var promises = data.filter(function(r) { return r._id; }).map(function(r) {
        return API.delete('/api/wbs/items/' + r._id);
    });
    Promise.all(promises).then(function() {
        data = [];
        renderGrid();
        showToast('초기화되었습니다.', 'success');
    }).catch(function() {
        showToast('초기화 실패', 'error');
    });
}

// ===== API Save =====
var pendingSaves = {};

function saveField(id, col, value) {
    if (!id) return;
    var payload = {};
    if (col === 'effort') payload[col] = parseFloat(value) || 0;
    else if (col === 'progress') payload[col] = parseInt(value) || 0;
    else payload[col] = value;

    // Debounce per item
    if (pendingSaves[id]) clearTimeout(pendingSaves[id]);
    pendingSaves[id] = setTimeout(function() {
        API.patch('/api/wbs/items/' + id, payload).then(function() {
            document.getElementById('footerSaved').textContent = new Date().toLocaleTimeString('ko-KR');
        }).catch(function() {
            showToast('저장 실패', 'error');
        });
        delete pendingSaves[id];
    }, 300);
}

function saveBatch() {
    var items = [];
    for (var i = 0; i < data.length; i++) {
        var r = data[i];
        if (r._id) {
            var obj = { id: r._id };
            COLUMNS.forEach(function(c) { obj[c] = r[c] || ''; });
            obj.effort = parseFloat(obj.effort) || 0;
            obj.progress = parseInt(obj.progress) || 0;
            items.push(obj);
        } else {
            // Create new items
            var apiData = {};
            COLUMNS.forEach(function(c) { apiData[c] = r[c] || ''; });
            apiData.effort = parseFloat(apiData.effort) || 0;
            apiData.progress = parseInt(apiData.progress) || 0;
            (function(row) {
                API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
                    row._id = item.id;
                });
            })(r);
        }
    }
    if (items.length > 0) {
        API.post('/api/wbs/' + PROJECT_ID + '/items/batch', { items: items }).then(function() {
            document.getElementById('footerSaved').textContent = new Date().toLocaleTimeString('ko-KR');
        }).catch(function() {
            showToast('일괄 저장 실패', 'error');
        });
    }
}

// ===== Paste Modal =====
function showPasteModal() {
    document.getElementById('pasteModal').classList.add('show');
    document.getElementById('pasteArea').value = '';
    setTimeout(function() { document.getElementById('pasteArea').focus(); }, 100);
}

function closePasteModal() {
    document.getElementById('pasteModal').classList.remove('show');
}

function importPaste() {
    var t = document.getElementById('pasteArea').value;
    if (!t.trim()) return;
    var rows = t.split('\n');
    var created = [];
    for (var i = 0; i < rows.length; i++) {
        if (!rows[i].trim()) continue;
        var cells = rows[i].split('\t');
        var obj = newRow();
        for (var j = 0; j < cells.length && j < COLUMNS.length; j++) {
            obj[COLUMNS[j]] = cells[j].trim();
        }
        data.push(obj);
        created.push(obj);
    }
    // Save all new rows to API
    created.forEach(function(row) {
        var apiData = {};
        COLUMNS.forEach(function(c) { apiData[c] = row[c] || ''; });
        apiData.effort = parseFloat(apiData.effort) || 0;
        apiData.progress = parseInt(apiData.progress) || 0;
        API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
            row._id = item.id;
        });
    });
    closePasteModal();
    renderGrid();
    showToast(created.length + '개 행을 추가했습니다.', 'success');
}

// ===== Export =====
function exportCSV() {
    window.open('/api/io/' + PROJECT_ID + '/export/csv', '_blank');
}

function exportExcel() {
    window.open('/api/io/' + PROJECT_ID + '/export/excel', '_blank');
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', loadItems);
