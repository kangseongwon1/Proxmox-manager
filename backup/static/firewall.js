// 전역 함수로 정의
function loadFirewallGroups() {
    $('#main-content').html('<div class="text-center py-5"><i class="fas fa-spinner fa-spin fa-2x"></i><br>로딩 중...</div>');
    $.get('/firewall/groups', function(data) {
      $.get('/firewall/groups/content', function(html) {
        $('#main-content').html(html);
        renderGroups(data.groups || []);
      });
    });
}

  function renderGroups(groups) {
    const $tbody = $('#fw-group-tbody');
    $tbody.empty();
    if (!groups.length) {
      $tbody.append('<tr><td colspan="4" class="text-center text-muted">등록된 방화벽 그룹이 없습니다.</td></tr>');
      return;
    }
    groups.forEach(g => {
      $tbody.append(`
        <tr>
          <td class="fw-bold">${g.name}</td>
          <td>${g.description || ''}</td>
          <td>${g.instance_count || 0}</td>
          <td>
            <button class="btn btn-outline-primary btn-sm fw-detail-btn" data-group="${g.name}"><i class="fas fa-list"></i> 상세</button>
            <button class="btn btn-outline-danger btn-sm fw-delete-btn" data-group="${g.name}"><i class="fas fa-trash"></i> 삭제</button>
          </td>
        </tr>
      `);
    });
  }

// 전역 함수로 정의
function loadFirewallGroupDetail(group) {
    $('#main-content').html('<div class="text-center py-5"><i class="fas fa-spinner fa-spin fa-2x"></i><br>로딩 중...</div>');
    $.get(`/firewall/groups/${group}/rules`, function(data) {
      $.get('/firewall/group-detail/content', function(html) {
        $('#main-content').html(html);
        $('#fw-group-title').text(`방화벽 그룹: ${data.group.name}`);
        $('#fw-group-desc').text(data.group.description || '');
        renderRules(data.rules || []);
      });
    });
}

  function renderRules(rules) {
    const $tbody = $('#fw-rule-tbody');
    $tbody.empty();
    if (!rules.length) {
      $tbody.append('<tr><td colspan="6" class="text-center text-muted">등록된 규칙이 없습니다.</td></tr>');
      return;
    }
    rules.forEach(r => {
      $tbody.append(`
        <tr>
          <td>${r.direction}</td>
          <td>${r.protocol}</td>
          <td>${r.port}</td>
          <td>${r.source || r.target || ''}</td>
          <td>${r.description || ''}</td>
          <td><button class="btn btn-outline-danger btn-sm fw-rule-delete-btn" data-rule-id="${r.id}"><i class="fas fa-trash"></i> 삭제</button></td>
        </tr>
      `);
    });
  }

// 이벤트 리스너들을 document.ready로 감싸기
$(function() {
  loadFirewallGroups();
  // 상세 버튼 클릭 시 상세 페이지로 이동
  $(document).on('click', '.fw-detail-btn', function() {
    const group = $(this).data('group');
    location.hash = `#firewall-group-${group}`;
  });

  // 규칙 추가 버튼 클릭 시 모달 표시
  $(document).on('click', '#fw-rule-add-btn', function() {
    showRuleAddModal();
  });

  function showRuleAddModal() {
    const modalHtml = `
      <div class="modal fade" id="fw-rule-add-modal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title"><i class="fas fa-plus me-2"></i>규칙 추가</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <form id="fw-rule-add-form">
                <div class="mb-2">
                  <label class="form-label">방향</label>
                  <select class="form-select" name="direction" required>
                    <option value="in">IN (수신)</option>
                    <option value="out">OUT (발신)</option>
                  </select>
                </div>
                <div class="mb-2">
                  <label class="form-label">프로토콜</label>
                  <select class="form-select" name="protocol" required>
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="icmp">ICMP</option>
                  </select>
                </div>
                <div class="mb-2">
                  <label class="form-label">포트</label>
                  <input type="text" class="form-control" name="port" placeholder="예: 80, 22, 1000:2000" required>
                </div>
                <div class="mb-2">
                  <label class="form-label">소스/대상</label>
                  <input type="text" class="form-control" name="source" placeholder="예: 0.0.0.0/0, 192.168.0.0/24">
                </div>
                <div class="mb-2">
                  <label class="form-label">설명</label>
                  <input type="text" class="form-control" name="description">
                </div>
              </form>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="submit" class="btn btn-primary" form="fw-rule-add-form">추가</button>
            </div>
          </div>
        </div>
      </div>
    `;
    $(modalHtml).appendTo('body');
    const $modal = $('#fw-rule-add-modal');
    $modal.modal('show');
    $modal.on('hidden.bs.modal', function() { $modal.remove(); });
  }

  // 규칙 추가 폼 제출
  $(document).on('submit', '#fw-rule-add-form', function(e) {
    e.preventDefault();
    const group = decodeURIComponent(location.hash.replace('#firewall-group-', ''));
    const data = $(this).serialize();
    $.post(`/firewall/groups/${group}/rules`, data, function(resp) {
      if (resp.success) {
        $('.modal').modal('hide');
        loadFirewallGroupDetail(group);
      } else {
        alert(resp.error || '규칙 추가 실패');
      }
    });
  });

  // 규칙 삭제 버튼 클릭
  $(document).on('click', '.fw-rule-delete-btn', function() {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    const group = decodeURIComponent(location.hash.replace('#firewall-group-', ''));
    const ruleId = $(this).data('rule-id');
    $.ajax({
      url: `/firewall/groups/${group}/rules/${ruleId}`,
      type: 'DELETE',
      success: function(resp) {
        if (resp.success) {
          loadFirewallGroupDetail(group);
        } else {
          alert(resp.error || '규칙 삭제 실패');
        }
      }
    });
  });

  // 신규 그룹 추가, 상세, 삭제 등 이벤트 핸들러는 추후 구현
  
  // 목록으로 돌아가기 버튼
  $(document).on('click', '#fw-group-list-btn', function() {
    location.hash = '#firewall-groups';
  });
  
  // 모달 생성 전 기존 모달 제거
  function removeExistingModal(modalId) {
    const $modal = $(modalId);
    if ($modal.length) {
      $modal.modal('hide');
      $modal.remove();
    }
  }
  // 새 그룹 추가 버튼 클릭 시 모달 표시
  $(document).on('click', '#add-fw-group-btn', function() {
    removeExistingModal('#fw-group-add-modal');
    const modalHtml = `
      <div class="modal fade" id="fw-group-add-modal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title"><i class="fas fa-plus me-2"></i>새 그룹 추가</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <form id="fw-group-add-form">
                <div class="mb-2">
                  <label class="form-label">그룹명</label>
                  <input type="text" class="form-control" name="name" required maxlength="32">
                </div>
                <div class="mb-2">
                  <label class="form-label">설명</label>
                  <input type="text" class="form-control" name="description" maxlength="100">
                </div>
              </form>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="submit" class="btn btn-primary" form="fw-group-add-form">추가</button>
            </div>
          </div>
        </div>
      </div>
    `;
    $(modalHtml).appendTo('body');
    const $modal = $('#fw-group-add-modal');
    $modal.modal('show');
    $modal.on('hidden.bs.modal', function() { $modal.remove(); });
  });
  
  // 새 그룹 추가 폼 제출
  $(document).on('submit', '#fw-group-add-form', function(e) {
    e.preventDefault();
    const data = $(this).serialize();
    $.post('/firewall/groups', data, function(resp) {
      if (resp.success) {
        $('.modal').modal('hide');
        loadFirewallGroups();
      } else {
        alert(resp.error || '그룹 추가 실패');
      }
    });
  });
  
  // 그룹 삭제 버튼 클릭 시 모달 중복 방지
  $(document).on('click', '.fw-delete-btn', function() {
    removeExistingModal('#fw-group-delete-modal');
    const group = $(this).data('group');
    const modalHtml = `
      <div class="modal fade" id="fw-group-delete-modal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title"><i class="fas fa-trash me-2"></i>그룹 삭제</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-2">정말 <b>${group}</b> 그룹을 삭제하시겠습니까?</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="button" class="btn btn-danger" id="fw-group-delete-confirm-btn" data-group="${group}">삭제</button>
            </div>
          </div>
        </div>
      </div>
    `;
    $(modalHtml).appendTo('body');
    const $modal = $('#fw-group-delete-modal');
    $modal.modal('show');
    $modal.on('hidden.bs.modal', function() { $modal.remove(); });
  });

  // 삭제 확인 버튼 클릭
  $(document).off('click', '#fw-group-delete-confirm-btn').on('click', '#fw-group-delete-confirm-btn', function() {
    const group = $(this).data('group');
    $.ajax({
      url: `/firewall/groups/${encodeURIComponent(group)}`,
      type: 'DELETE',
      success: function(resp) {
        $('.modal').modal('hide');
        loadFirewallGroups();
      }
    });
  });

  // 규칙 추가/삭제 모달 닫힘 보장
  $(document).on('hidden.bs.modal', '.modal', function() { $(this).remove(); });
});