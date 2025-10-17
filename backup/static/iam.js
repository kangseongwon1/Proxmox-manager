// iam.js
$(function() {
  console.log('[iam.js] iam.js loaded');
  let PERMISSIONS = [];
  let USERS = {};
  let overlayUser = null;
  let selectedPerms = [];

  function showIAMAlert(type, msg) {
    const alert = $('#iam-alert');
    alert.removeClass('d-none alert-success alert-danger alert-info').addClass('alert-' + type).html(`<i class="fas fa-info-circle me-2"></i>${msg}`).fadeIn(200);
    setTimeout(() => alert.fadeOut(200), 2000);
    
    // 전역 알림 시스템에도 추가
    if (typeof window.addSystemNotification === 'function') {
      window.addSystemNotification(type, '사용자 관리', msg);
    }
  }

  function renderSummary() {
    const users = Object.values(USERS);
    const total = users.length;
    const admin = users.filter(u=>u.role==='admin').length;
    const dev = users.filter(u=>u.role==='developer').length;
    const op = users.filter(u=>u.role==='operator').length;
    const viewer = users.filter(u=>u.role==='viewer').length;
    const html = `
      <div class='row g-3 mb-3'>
        <div class='col'><div class='card text-center border-primary h-100'><div class='card-body'><div class='fw-bold text-primary mb-1'><i class='fas fa-users'></i> 전체 사용자</div><div class='fs-3'>${total}</div></div></div></div>
        <div class='col'><div class='card text-center border-success h-100'><div class='card-body'><div class='fw-bold text-success mb-1'><i class='fas fa-user-crown'></i> 관리자</div><div class='fs-3'>${admin}</div></div></div></div>
        <div class='col'><div class='card text-center border-info h-100'><div class='card-body'><div class='fw-bold text-info mb-1'><i class='fas fa-user-gear'></i> 개발자</div><div class='fs-3'>${dev}</div></div></div></div>
        <div class='col'><div class='card text-center border-warning h-100'><div class='card-body'><div class='fw-bold text-warning mb-1'><i class='fas fa-user-cog'></i> 오퍼레이터</div><div class='fs-3'>${op}</div></div></div></div>
        <div class='col'><div class='card text-center border-secondary h-100'><div class='card-body'><div class='fw-bold text-secondary mb-1'><i class='fas fa-user'></i> 뷰어</div><div class='fs-3'>${viewer}</div></div></div></div>
      </div>
    `;
    $('#iam-summary-row').html(html);
  }

  function renderTable() {
    const tbody = $('#iam-user-tbody');
    tbody.empty();
    Object.entries(USERS).forEach(([username, user]) => {
      const isAdmin = user.role === 'admin';
      const isInactive = user.is_active === false;
      let tr = $('<tr>').toggleClass('iam-admin-row', isAdmin).toggleClass('table-secondary', isInactive).addClass('iam-user-row').attr('data-username', username);
      
      // ===== 테이블 컬럼 너비 설정 (admin_iam_content.html의 th와 일치해야 함) =====
      tr.append(`<td class="align-middle text-center" style="width:48px;"><i class="fas fa-user-circle iam-profile-icon ${isInactive ? 'text-muted' : ''}"></i></td>`); // 프로필 아이콘
      tr.append(`<td class="fw-bold align-middle" style="width:80px;">${username} ${isInactive ? '<span class="badge bg-secondary ms-1">비활성</span>' : ''}</td>`); // 사용자명
      tr.append(`<td class="align-middle" style="width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:0.97em;">${user.email || ''}</td>`); // 이메일
      
      // 역할 배지 색상 설정
      let roleBadge = {
        'admin': 'bg-success',
        'developer': 'bg-info',
        'operator': 'bg-warning',
        'viewer': 'bg-secondary'
      }[user.role] || 'bg-light';
      let roleSel = `<div class="d-flex align-items-center gap-2"><span class="badge ${roleBadge}">${user.role}</span></div>`;
      tr.append(`<td class="align-middle text-center" style="width:110px;"><span class="badge ${user.role === 'admin' ? 'bg-success' : 'bg-info'}">${user.role}</span></td>`); // 역할
      tr.append(`<td class="align-middle text-center" style="width:140px;"><button class="btn btn-outline-primary btn-sm iam-expand-btn" data-username="${username}" title="권한 관리"><i class="fas fa-edit"></i> 권한관리</button></td>`); // 권한관리
      tr.append(`<td class="align-middle text-center" style="width:80px;"><button class="btn btn-outline-secondary btn-sm iam-password-btn" data-username="${username}" title="비밀번호 변경"><i class="fas fa-key"></i></button></td>`); // 비밀번호 변경
      tr.append(`<td class="align-middle text-center" style="width:60px;">${user.role !== 'admin' ? `<button class="btn btn-outline-danger btn-sm iam-delete-btn" data-username="${username}" title="사용자 삭제"><i class="fas fa-trash"></i></button>` : ''}</td>`); // 삭제
  
      // ===== 테이블 컬럼 너비 설정 끝 =====
      
      tbody.append(tr);
    });
    tbody.find('tr.iam-user-row').hover(
      function() { $(this).addClass('table-primary'); },
      function() { $(this).removeClass('table-primary'); }
    );
  }

  // 오버레이 권한 카드 렌더링 (개선된 UI)
  function renderPermCardsOverlay(username) {
    const user = USERS[username];
    if (!user) return '';
    let perms = selectedPerms.length ? selectedPerms : user.permissions;
    // 왼쪽: 부여되지 않은 권한, 오른쪽: 부여된 권한
    const unassigned = PERMISSIONS.filter(p => !perms.includes(p));
    const assigned = perms;
    
    // ===== 권한 설명 매핑 (새로운 권한 추가 시 여기에 추가) =====
    const permDescriptions = {
      'view_all': '모든 리소스 조회',
      'create_server': '서버 생성',
      'delete_server': '서버 삭제',
      'start_server': '서버 시작',
      'stop_server': '서버 중지',
      'manage_users': '사용자 관리',
      'manage_roles': '역할 관리',
      'view_logs': '로그 조회',
      'manage_storage': '스토리지 관리',
      'manage_network': '네트워크 관리'
      // 새로운 권한 추가 예시:
      // 'new_permission': '새로운 권한 설명'
    };
    // ===== 권한 설명 매핑 끝 =====
    
    let html = `
      <div class="iam-overlay-header mb-4">
        <div class="d-flex align-items-center">
          <div class="iam-user-avatar me-3">
            <i class="fas fa-user-circle fa-3x text-primary"></i>
          </div>
          <div>
            <h5 class="mb-1">${username}</h5>
            <div class="d-flex align-items-center gap-2">
              <span class="badge ${user.role==='admin'?'bg-success':user.role==='developer'?'bg-info':user.role==='operator'?'bg-warning':'bg-secondary'} fs-6">${user.role}</span>
              <span class="text-muted">${user.email || ''}</span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="iam-permissions-container">
        <div class="row g-4">
          <!-- 권한 풀 -->
          <div class="col-md-6">
            <div class="iam-perm-section">
              <div class="iam-section-header">
                <i class="fas fa-plus-circle text-primary me-2"></i>
                <h6 class="mb-0">사용 가능한 권한</h6>
                <span class="badge bg-primary ms-2">${unassigned.length}</span>
              </div>
              <div id="perm-pool-list" class="iam-perm-list">
                ${unassigned.length > 0 ? unassigned.map(perm => `
                  <div class="iam-perm-item" data-perm="${perm}" draggable="true">
                    <div class="iam-perm-content">
                      <i class="fas fa-key text-primary me-2"></i>
                      <div class="iam-perm-info">
                        <div class="iam-perm-name">${perm}</div>
                        <div class="iam-perm-desc">${permDescriptions[perm] || '권한 설명'}</div>
                      </div>
                      <i class="fas fa-arrow-right text-muted"></i>
                    </div>
                  </div>
                `).join('') : '<div class="iam-empty-state"><i class="fas fa-check-circle text-success fa-2x mb-2"></i><div>모든 권한이 부여되었습니다</div></div>'}
              </div>
            </div>
          </div>
          
          <!-- 부여된 권한 -->
          <div class="col-md-6">
            <div class="iam-perm-section">
              <div class="iam-section-header">
                <i class="fas fa-check-circle text-success me-2"></i>
                <h6 class="mb-0">부여된 권한</h6>
                <span class="badge bg-success ms-2">${assigned.length}</span>
              </div>
              <div id="perm-assigned-list" class="iam-perm-list">
                ${assigned.length > 0 ? assigned.map(perm => `
                  <div class="iam-perm-item assigned" data-perm="${perm}" draggable="true">
                    <div class="iam-perm-content">
                      <i class="fas fa-key text-success me-2"></i>
                      <div class="iam-perm-info">
                        <div class="iam-perm-name">${perm}</div>
                        <div class="iam-perm-desc">${permDescriptions[perm] || '권한 설명'}</div>
                      </div>
                      <i class="fas fa-arrow-left text-muted"></i>
                    </div>
                  </div>
                `).join('') : '<div class="iam-empty-state"><i class="fas fa-exclamation-circle text-warning fa-2x mb-2"></i><div>부여된 권한이 없습니다</div></div>'}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="iam-overlay-footer mt-4">
        <div class="d-flex justify-content-between align-items-center">
          <div class="iam-help-text">
            <i class="fas fa-info-circle text-info me-1"></i>
            <small class="text-muted">드래그하거나 클릭하여 권한을 이동할 수 있습니다</small>
          </div>
          <div class="iam-actions">
            <button class="btn btn-outline-secondary btn-sm me-2" id="iam-cancel-btn">
              <i class="fas fa-times me-1"></i>취소
            </button>
            <button class="btn btn-success btn-sm iam-save-perm-btn" data-username="${username}" disabled>
              <i class="fas fa-save me-1"></i>변경사항 적용
            </button>
          </div>
        </div>
      </div>
    `;
    return html;
  }

  function loadIAM() {
    console.log('[iam.js] loadIAM 호출');
    $('#iam-loading').removeClass('d-none');
    $.get('/admin/iam', function(res) {
      console.log('[iam.js] /admin/iam 응답:', res);
      USERS = res.users;
      PERMISSIONS = res.permissions;
      renderSummary();
      renderTable();
      $('#iam-loading').addClass('d-none');
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay').hide();
      $('#iam-overlay-content').empty();
    }).fail(function(xhr) {
      console.error('[iam.js] /admin/iam 실패:', xhr);
      let errorMsg = '사용자 목록을 불러올 수 없습니다.';
      
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 관리자 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      showIAMAlert('danger', errorMsg);
    });
  }

  // 권한 관리 버튼 클릭 시 오버레이 띄우기
  $(document).off('click', '.iam-expand-btn').on('click', '.iam-expand-btn', function(e) {
    console.log('[iam.js] .iam-expand-btn 클릭', $(this).data('username'));
    e.stopPropagation();
    const username = $(this).data('username');
    overlayUser = username;
    selectedPerms = [...USERS[username].permissions];
    const html = renderPermCardsOverlay(username);
    $('#iam-overlay-content').html(html);
    $('#iam-overlay').fadeIn(120);
  });

  // 오버레이 닫기
  $(document).off('click', '#iam-overlay-close').on('click', '#iam-overlay-close', function() {
    console.log('[iam.js] #iam-overlay-close 클릭');
    $('#iam-overlay').fadeOut(120);
    overlayUser = null;
    selectedPerms = [];
    $('#iam-overlay-content').empty();
  });

  // 오버레이 바깥 클릭 시 닫기
  $(document).off('mousedown', '#iam-overlay').on('mousedown', '#iam-overlay', function(e) {
    if (e.target === this) {
      console.log('[iam.js] #iam-overlay 바깥 클릭');
      $('#iam-overlay').fadeOut(120);
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay-content').empty();
    }
  });

  // 새로운 권한 아이템 드래그 앤 드롭
  let dragPerm = null;
  $(document).off('dragstart', '.iam-perm-item').on('dragstart', '.iam-perm-item', function(e) {
    dragPerm = $(this).data('perm');
    $(this).addClass('dragging');
  });
  $(document).off('dragend', '.iam-perm-item').on('dragend', '.iam-perm-item', function(e) {
    dragPerm = null;
    $(this).removeClass('dragging');
  });
  
  // 드롭 영역 설정
  $(document).off('dragover', '.iam-perm-list').on('dragover', '.iam-perm-list', function(e) {
    e.preventDefault();
    $(this).addClass('drag-over');
  });
  $(document).off('dragleave', '.iam-perm-list').on('dragleave', '.iam-perm-list', function(e) {
    $(this).removeClass('drag-over');
  });
  $(document).off('drop', '.iam-perm-list').on('drop', '.iam-perm-list', function(e) {
    e.preventDefault();
    $(this).removeClass('drag-over');
    if (!dragPerm) return;
    
    const isAssignedList = $(this).attr('id') === 'perm-assigned-list';
    const isPoolList = $(this).attr('id') === 'perm-pool-list';
    
    if (isAssignedList && !selectedPerms.includes(dragPerm)) {
      // 권한 풀 → 부여된 권한
      selectedPerms.push(dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    } else if (isPoolList && selectedPerms.includes(dragPerm)) {
      // 부여된 권한 → 권한 풀
      selectedPerms = selectedPerms.filter(p => p !== dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });
  
  // 클릭으로 권한 이동
  $(document).off('click', '.iam-perm-item').on('click', '.iam-perm-item', function() {
    const perm = $(this).data('perm');
    const isAssigned = $(this).hasClass('assigned');
    
    if (isAssigned) {
      // 부여된 권한 → 권한 풀
      if (selectedPerms.includes(perm)) {
        selectedPerms = selectedPerms.filter(p => p !== perm);
        const html = renderPermCardsOverlay(overlayUser);
        $('#iam-overlay-content').html(html);
        $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
      }
    } else {
      // 권한 풀 → 부여된 권한
      if (!selectedPerms.includes(perm)) {
        selectedPerms.push(perm);
        const html = renderPermCardsOverlay(overlayUser);
        $('#iam-overlay-content').html(html);
        $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
      }
    }
  });
  
  // 취소 버튼
  $(document).off('click', '#iam-cancel-btn').on('click', '#iam-cancel-btn', function() {
    $('#iam-overlay').fadeOut(120);
    overlayUser = null;
    selectedPerms = [];
    $('#iam-overlay-content').empty();
  });

  // 권한 저장 버튼 클릭 (오버레이 내부)
  $(document).off('click', '.iam-save-perm-btn').on('click', '.iam-save-perm-btn', function() {
    console.log('[iam.js] .iam-save-perm-btn 클릭', $(this).data('username'), selectedPerms);
    const username = $(this).data('username');
    $.ajax({
      url: `/admin/iam/${username}/permissions`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ permissions: selectedPerms }),
      beforeSend: function() {
        console.log('[iam.js] /admin/iam/permissions 요청 전', username, selectedPerms);
      },
      success: function(res) {
        console.log('[iam.js] /admin/iam/permissions 성공', res);
        showIAMAlert('success', res.message);
        loadIAM();
      },
      error: function(xhr) {
        console.error('[iam.js] /admin/iam/permissions 실패', xhr);
        let errorMsg = '권한 변경 실패';
        
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 사용자 관리 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        showIAMAlert('danger', errorMsg);
      }
    });
  });

  // 사용자 추가 버튼 클릭
  $(document).off('click', '#add-user-btn').on('click', '#add-user-btn', function() {
    console.log('[iam.js] #add-user-btn 클릭');
    $('#add-user-modal').modal('show');
  });

  // 사용자 추가 저장 버튼 클릭
  $(document).off('click', '#save-user-btn').on('click', '#save-user-btn', function() {
    console.log('[iam.js] #save-user-btn 클릭');
    addNewUser();
  });

  // 사용자 추가 함수
  function addNewUser() {
    const formData = {
      username: $('#new-username').val().trim(),
      password: $('#new-password').val(),
      confirm_password: $('#new-confirm-password').val(),
      name: $('#new-name').val().trim(),
      email: $('#new-email').val().trim(),
      role: $('#new-role').val()
    };

    // 유효성 검사
    if (!formData.username) {
      showIAMAlert('danger', '사용자명을 입력해주세요.');
      return;
    }
    if (!formData.password) {
      showIAMAlert('danger', '비밀번호를 입력해주세요.');
      return;
    }
    if (formData.password !== formData.confirm_password) {
      showIAMAlert('danger', '비밀번호가 일치하지 않습니다.');
      return;
    }
    if (formData.password.length < 6) {
      showIAMAlert('danger', '비밀번호는 최소 6자 이상이어야 합니다.');
      return;
    }

    // 기본 권한 설정
    formData.permissions = ['view_all'];

    console.log('[iam.js] 새 사용자 추가 요청:', formData);

    $.ajax({
      url: '/users',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(formData),
      success: function(res) {
        console.log('[iam.js] 사용자 추가 성공:', res);
        showIAMAlert('success', res.message);
        $('#add-user-modal').modal('hide');
        resetAddUserForm();
        loadIAM(); // 목록 새로고침
      },
      error: function(xhr) {
        console.error('[iam.js] 사용자 추가 실패:', xhr);
        let errorMsg = '사용자 추가 실패';
        
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 사용자 관리 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        showIAMAlert('danger', errorMsg);
      }
    });
  }

  // 사용자 추가 폼 초기화
  function resetAddUserForm() {
    $('#add-user-form')[0].reset();
    $('#new-username').focus();
  }

  // 사용자 삭제 버튼 클릭
  $(document).off('click', '.iam-delete-btn').on('click', '.iam-delete-btn', function() {
    const username = $(this).data('username');
    console.log('[iam.js] .iam-delete-btn 클릭', username);
    
    if (confirm(`정말로 사용자 '${username}'을(를) 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.`)) {
      deleteUser(username);
    }
  });

  // 사용자 삭제 함수
  function deleteUser(username) {
    console.log('[iam.js] 사용자 삭제 요청:', username);
    
    $.ajax({
      url: `/users/${username}`,
      method: 'DELETE',
      success: function(res) {
        console.log('[iam.js] 사용자 삭제 성공:', res);
        showIAMAlert('success', res.message);
        loadIAM(); // 목록 새로고침
      },
      error: function(xhr) {
        console.error('[iam.js] 사용자 삭제 실패:', xhr);
        let errorMsg = '사용자 삭제 실패';
        
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 사용자 관리 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        showIAMAlert('danger', errorMsg);
      }
    });
  }

  // 비밀번호 변경 버튼 클릭
  $(document).off('click', '.iam-password-btn').on('click', '.iam-password-btn', function() {
    const username = $(this).data('username');
    const user = USERS[username];
    $('#iam-password-username').val(username);
    $('#iam-new-password').val('');
    $('#iam-confirm-password').val('');
    $('#iam-password-alert').addClass('d-none').text('');
    // 사용자 정보 표시
    $('#iam-password-userinfo').html(`
      <i class='fas fa-user-circle text-primary me-1'></i><b>${username}</b>
      <span class='text-muted ms-2'>${user.email || ''}</span>
      <span class='badge bg-${user.role==='admin'?'success':user.role==='developer'?'info':user.role==='operator'?'warning':'secondary'} ms-2'>${user.role}</span>
    `);
    $('#iam-password-modal').modal('show');
  });
  // 비밀번호 변경 저장 버튼 클릭
  $(document).off('click', '#iam-password-save-btn').on('click', '#iam-password-save-btn', function() {
    const username = $('#iam-password-username').val();
    const newPassword = $('#iam-new-password').val();
    const confirmPassword = $('#iam-confirm-password').val();
    const alert = $('#iam-password-alert');
    alert.addClass('d-none').removeClass('alert-success alert-danger').text('');
    if (!newPassword || !confirmPassword) {
      alert.removeClass('d-none').addClass('alert-danger').text('새 비밀번호와 확인을 입력해주세요.');
      return;
    }
    if (newPassword !== confirmPassword) {
      alert.removeClass('d-none').addClass('alert-danger').text('새 비밀번호가 일치하지 않습니다.');
      return;
    }
    if (newPassword.length < 6) {
      alert.removeClass('d-none').addClass('alert-danger').text('새 비밀번호는 최소 6자 이상이어야 합니다.');
      return;
    }
    $.ajax({
      url: `/users/${username}/password`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ new_password: newPassword, confirm_password: confirmPassword }),
      success: function(res) {
        alert.removeClass('d-none alert-danger').addClass('alert-success').text(res.message);
        setTimeout(function() {
          $('#iam-password-modal').modal('hide');
        }, 1500);
        showIAMAlert('success', res.message);
      },
      error: function(xhr) {
        let errorMsg = xhr.responseJSON?.error || '비밀번호 변경 실패';
        alert.removeClass('d-none alert-success').addClass('alert-danger').text(errorMsg);
        showIAMAlert('danger', errorMsg);
      }
    });
  });
  // 모달 닫힐 때 폼 초기화
  $('#iam-password-modal').on('hidden.bs.modal', function() {
    $('#iam-password-form')[0].reset();
    $('#iam-password-alert').addClass('d-none').text('');
  });

  // 모달 닫힐 때 폼 초기화
  $('#add-user-modal').on('hidden.bs.modal', function() {
    resetAddUserForm();
  });

  // 초기 로드
  loadIAM();
}); 