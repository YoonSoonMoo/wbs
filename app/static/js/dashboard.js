// ===== Dashboard =====
var editingProjectId = null;
var availableUsers = [];

async function loadProjects() {
    try {
        var projects = await API.get('/api/projects');
        renderProjects(projects);
    } catch (e) {
        document.getElementById('project-list').innerHTML =
            '<div class="empty-state"><p>프로젝트를 불러올 수 없습니다.</p></div>';
    }
}

async function renderProjects(projects) {
    var container = document.getElementById('project-list');
    var isAdmin = (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin');

    if (projects.length === 0) {
        var emptyHtml = '<div class="empty-state"><p>아직 프로젝트가 없습니다.</p>';
        if (isAdmin) emptyHtml += '<button class="btn btn-primary" onclick="showCreateProjectModal()">첫 프로젝트 만들기</button>';
        emptyHtml += '</div>';
        container.innerHTML = emptyHtml;
        return;
    }

    var html = '';
    for (var i = 0; i < projects.length; i++) {
        var project = projects[i];
        var stats = { total: 0, completed: 0, in_progress: 0, delayed: 0, avg_progress: 0 };
        try {
            stats = await API.get('/api/wbs/' + project.id + '/stats');
        } catch (e) { /* ignore */ }

        html += '<div class="project-card" onclick="location.href=\'/project/' + project.id + '/wbs\'">';
        html += '<h3>' + escapeHtml(project.name) + '</h3>';
        html += '<div class="desc">' + escapeHtml(project.description || '설명 없음') + '</div>';
        html += '<div class="meta"><span>' + (project.start_date || '-') + ' ~ ' + (project.end_date || '-') + '</span></div>';
        html += '<div class="progress-bar"><div class="progress-bar-fill" style="width:' + stats.avg_progress + '%"></div></div>';
        html += '<div class="stats">';
        html += '<div class="stat-item"><div class="stat-value">' + stats.total + '</div><div class="stat-label">전체</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.completed + '</div><div class="stat-label">완료</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.in_progress + '</div><div class="stat-label">진행중</div></div>';
        html += '<div class="stat-item"><div class="stat-value" style="color:' + (stats.delayed > 0 ? 'var(--danger)' : '') + '">' + stats.delayed + '</div><div class="stat-label">지연</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.avg_progress + '%</div><div class="stat-label">진행률</div></div>';
        html += '</div>';

        if (isAdmin) {
            html += '<div class="project-actions" onclick="event.stopPropagation()">';
            html += '<button class="btn" onclick="editProject(' + project.id + ')">수정</button>';
            html += '<button class="btn" style="color:var(--danger)" onclick="clearProjectData(' + project.id + ', \'' + escapeHtml(project.name).replace(/'/g, "\\'") + '\')">데이터 초기화</button>';
            html += '<button class="btn" style="color:var(--danger)" onclick="deleteProject(' + project.id + ', \'' + escapeHtml(project.name).replace(/'/g, "\\'") + '\')">삭제</button>';
            html += '</div>';
        }

        html += '</div>';
    }
    container.innerHTML = html;
}

// ===== Modal =====
async function showCreateProjectModal() {
    editingProjectId = null;
    document.getElementById('modal-title').textContent = '새 프로젝트';
    document.getElementById('project-form').reset();
    document.getElementById('project-id').value = '';
    clearMemberList();
    await loadAvailableUsers();
    document.getElementById('project-modal').style.display = 'flex';
}

async function editProject(id) {
    try {
        var project = await API.get('/api/projects/' + id);
        editingProjectId = id;
        document.getElementById('modal-title').textContent = '프로젝트 수정';
        document.getElementById('project-id').value = id;
        document.getElementById('project-name').value = project.name;
        document.getElementById('project-desc').value = project.description || '';
        document.getElementById('project-start').value = project.start_date || '';
        document.getElementById('project-end').value = project.end_date || '';

        clearMemberList();
        await loadAvailableUsers();
        // 기존 멤버 로드
        var members = await API.get('/api/projects/' + id + '/members');
        for (var i = 0; i < members.length; i++) {
            addMemberRow(members[i].id, members[i].role);
        }

        document.getElementById('project-modal').style.display = 'flex';
    } catch (e) {
        showToast('프로젝트를 불러올 수 없습니다.', 'error');
    }
}

function closeModal() {
    document.getElementById('project-modal').style.display = 'none';
}

async function handleProjectSubmit(e) {
    e.preventDefault();
    var data = {
        name: document.getElementById('project-name').value,
        description: document.getElementById('project-desc').value,
        start_date: document.getElementById('project-start').value || null,
        end_date: document.getElementById('project-end').value || null,
    };

    if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin') {
        data.members = collectMembers();
    }

    try {
        if (editingProjectId) {
            await API.put('/api/projects/' + editingProjectId, data);
            showToast('프로젝트가 수정되었습니다.', 'success');
        } else {
            await API.post('/api/projects', data);
            showToast('프로젝트가 생성되었습니다.', 'success');
        }
        closeModal();
        loadProjects();
    } catch (e) {
        showToast('저장에 실패했습니다.', 'error');
    }
}

async function deleteProject(id, name) {
    if (!confirm('"' + name + '" 프로젝트를 삭제하시겠습니까?\n모든 WBS 항목도 함께 삭제됩니다.')) return;
    try {
        await API.delete('/api/projects/' + id);
        showToast('프로젝트가 삭제되었습니다.', 'success');
        loadProjects();
    } catch (e) {
        showToast('삭제에 실패했습니다.', 'error');
    }
}

// ===== Data Reset =====
async function clearProjectData(id, name) {
    if (!confirm('"' + name + '" 프로젝트의 WBS 데이터를 모두 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) return;
    try {
        await API.delete('/api/wbs/' + id + '/items');
        showToast('WBS 데이터가 초기화되었습니다.', 'success');
        loadProjects();
    } catch (e) {
        showToast('초기화에 실패했습니다.', 'error');
    }
}

// ===== Member Assignment =====
async function loadAvailableUsers() {
    try {
        availableUsers = await API.get('/api/projects/users');
    } catch (e) {
        availableUsers = [];
    }
}

function clearMemberList() {
    var list = document.getElementById('member-list');
    if (list) list.innerHTML = '';
}

function addMemberRow(selectedUserId, selectedRole) {
    var list = document.getElementById('member-list');
    if (!list) return;

    var row = document.createElement('div');
    row.className = 'member-row';

    var userOptions = '';
    for (var i = 0; i < availableUsers.length; i++) {
        var u = availableUsers[i];
        var sel = (selectedUserId && u.id === selectedUserId) ? ' selected' : '';
        userOptions += '<option value="' + u.id + '"' + sel + '>' + escapeHtml(u.name) + ' (' + escapeHtml(u.email) + ')</option>';
    }

    var partSel = (!selectedRole || selectedRole === 'participant') ? ' selected' : '';
    var viewSel = (selectedRole === 'viewer') ? ' selected' : '';

    row.innerHTML = '<select class="member-user" style="flex:2;">' + userOptions + '</select>' +
        '<select class="member-role" style="flex:1;"><option value="participant"' + partSel + '>참여자</option><option value="viewer"' + viewSel + '>뷰어</option></select>' +
        '<button type="button" class="btn-remove" onclick="this.parentElement.remove()">&times;</button>';

    list.appendChild(row);
}

function collectMembers() {
    var rows = document.querySelectorAll('.member-row');
    var members = [];
    for (var i = 0; i < rows.length; i++) {
        var userId = rows[i].querySelector('.member-user');
        var role = rows[i].querySelector('.member-role');
        if (userId && role) {
            members.push({
                user_id: parseInt(userId.value),
                role: role.value,
            });
        }
    }
    return members;
}

// ===== Utility =====
function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', loadProjects);
