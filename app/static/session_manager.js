// session_manager.js - 세션 자동 갱신 및 관리
$(function() {
  console.log('[session_manager.js] 세션 관리자 초기화');
  
  // 세션 갱신 간격 (5분마다)
  const SESSION_REFRESH_INTERVAL = 5 * 60 * 1000; // 5분
  const SESSION_CHECK_INTERVAL = 30 * 1000; // 30초
  
  let sessionRefreshTimer = null;
  let sessionCheckTimer = null;
  let isRefreshing = false;
  
  // 세션 상태 확인
  function checkSessionStatus() {
    if (isRefreshing) return;
    
    $.ajax({
      url: '/api/session/check',
      method: 'GET',
      timeout: 10000,
      success: function(response) {
        if (response.authenticated) {
          console.log('[session_manager.js] 세션 유효함');
          // 세션이 유효하면 갱신 타이머 시작
          startSessionRefreshTimer();
        } else {
          console.log('[session_manager.js] 세션 만료됨');
          handleSessionExpired();
        }
      },
      error: function(xhr) {
        if (xhr.status === 401) {
          console.log('[session_manager.js] 세션 만료됨 (401)');
          handleSessionExpired();
        } else {
          console.log('[session_manager.js] 세션 상태 확인 실패:', xhr.status);
        }
      }
    });
  }
  
  // 세션 갱신
  function refreshSession() {
    if (isRefreshing) return;
    
    isRefreshing = true;
    console.log('[session_manager.js] 세션 갱신 시작');
    
    $.ajax({
      url: '/api/session/refresh',
      method: 'POST',
      timeout: 10000,
      success: function(response) {
        if (response.success) {
          console.log('[session_manager.js] 세션 갱신 성공');
          // 성공 알림 표시 (조용히)
          showSessionNotification('success', '세션이 갱신되었습니다.', 2000);
        } else {
          console.log('[session_manager.js] 세션 갱신 실패:', response.error);
          handleSessionExpired();
        }
      },
      error: function(xhr) {
        console.log('[session_manager.js] 세션 갱신 오류:', xhr.status);
        if (xhr.status === 401) {
          handleSessionExpired();
        }
      },
      complete: function() {
        isRefreshing = false;
      }
    });
  }
  
  // 세션 만료 처리
  function handleSessionExpired() {
    console.log('[session_manager.js] 세션 만료 처리 시작');
    
    // 타이머 정리
    stopSessionTimers();
    
    // 현재 페이지가 로그인 페이지가 아닌 경우에만 처리
    if (!window.location.pathname.includes('/auth/login')) {
      // 작업 중인 AJAX 요청이 있는지 확인
      if ($.active > 0) {
        console.log('[session_manager.js] 진행 중인 AJAX 요청이 있습니다. 잠시 후 다시 시도합니다.');
        setTimeout(handleSessionExpired, 2000);
        return;
      }
      
      // 사용자에게 알림
      showSessionNotification('warning', '세션이 만료되었습니다. 로그인 페이지로 이동합니다.', 3000);
      
      // 현재 작업 상태 저장 (선택사항)
      saveCurrentWorkState();
      
      // 3초 후 로그인 페이지로 리다이렉트
      setTimeout(function() {
        window.location.href = '/auth/login';
      }, 3000);
    }
  }
  
  // 세션 갱신 타이머 시작
  function startSessionRefreshTimer() {
    if (sessionRefreshTimer) {
      clearInterval(sessionRefreshTimer);
    }
    
    sessionRefreshTimer = setInterval(function() {
      refreshSession();
    }, SESSION_REFRESH_INTERVAL);
    
    console.log('[session_manager.js] 세션 갱신 타이머 시작 (5분 간격)');
  }
  
  // 세션 상태 확인 타이머 시작
  function startSessionCheckTimer() {
    if (sessionCheckTimer) {
      clearInterval(sessionCheckTimer);
    }
    
    sessionCheckTimer = setInterval(function() {
      checkSessionStatus();
    }, SESSION_CHECK_INTERVAL);
    
    console.log('[session_manager.js] 세션 상태 확인 타이머 시작 (30초 간격)');
  }
  
  // 모든 타이머 정리
  function stopSessionTimers() {
    if (sessionRefreshTimer) {
      clearInterval(sessionRefreshTimer);
      sessionRefreshTimer = null;
    }
    if (sessionCheckTimer) {
      clearInterval(sessionCheckTimer);
      sessionCheckTimer = null;
    }
    console.log('[session_manager.js] 모든 세션 타이머 정리됨');
  }
  
  // 세션 알림 표시
  function showSessionNotification(type, message, duration = 3000) {
    // 기존 세션 알림 제거
    $('.session-notification').remove();
    
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'warning' ? 'alert-warning' : 
                      type === 'error' ? 'alert-danger' : 'alert-info';
    
    const notification = $(`
      <div class="session-notification alert ${alertClass} alert-dismissible fade show position-fixed" 
           style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
        <i class="fas fa-${type === 'success' ? 'check-circle' : 
                         type === 'warning' ? 'exclamation-triangle' : 
                         type === 'error' ? 'times-circle' : 'info-circle'} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    `);
    
    $('body').append(notification);
    
    // 자동 제거
    setTimeout(function() {
      notification.fadeOut(function() {
        $(this).remove();
      });
    }, duration);
  }
  
  // 현재 작업 상태 저장 (선택사항)
  function saveCurrentWorkState() {
    try {
      // 폼 데이터 저장
      const formData = {};
      $('form').each(function() {
        const formId = $(this).attr('id') || 'form_' + Math.random().toString(36).substr(2, 9);
        formData[formId] = $(this).serialize();
      });
      
      // 서버 생성 폼 상태 저장
      if ($('#create-server-form').length > 0) {
        const serverFormState = {
          mode: $('#server_mode').val(),
          count: $('#multi-server-count').val(),
          name: $('input[name="name_basic"]').val(),
          os: $('#os-select').val(),
          role: $('#role-select').val(),
          cpu: $('input[name="cpu_basic"]').val(),
          memory: $('input[name="memory_basic"]').val()
        };
        localStorage.setItem('serverFormState', JSON.stringify(serverFormState));
      }
      
      // 현재 페이지 정보 저장
      localStorage.setItem('lastPage', window.location.pathname);
      localStorage.setItem('lastPageTitle', document.title);
      
      console.log('[session_manager.js] 작업 상태 저장 완료');
    } catch (e) {
      console.log('[session_manager.js] 작업 상태 저장 실패:', e);
    }
  }
  
  // 저장된 작업 상태 복원 (선택사항)
  function restoreWorkState() {
    try {
      // 서버 생성 폼 상태 복원
      const serverFormState = localStorage.getItem('serverFormState');
      if (serverFormState && $('#create-server-form').length > 0) {
        const state = JSON.parse(serverFormState);
        
        $('#server_mode').val(state.mode || 'single');
        $('#multi-server-count').val(state.count || '2');
        $('input[name="name_basic"]').val(state.name || '');
        $('#os-select').val(state.os || '');
        $('#role-select').val(state.role || '');
        $('input[name="cpu_basic"]').val(state.cpu || '2');
        $('input[name="memory_basic"]').val(state.memory || '2048');
        
        // 모드에 따른 UI 업데이트
        if (state.mode === 'multi') {
          $('.mode-card[data-mode="multi"]').addClass('active');
          $('#multi-server-options').show();
        }
        
        console.log('[session_manager.js] 서버 생성 폼 상태 복원 완료');
      }
    } catch (e) {
      console.log('[session_manager.js] 작업 상태 복원 실패:', e);
    }
  }
  
  // 페이지 로드 시 세션 관리 시작
  function initializeSessionManager() {
    console.log('[session_manager.js] 세션 관리자 초기화 시작');
    
    // 현재 페이지가 로그인 페이지가 아닌 경우에만 세션 관리 시작
    if (!window.location.pathname.includes('/auth/login')) {
      // 초기 세션 상태 확인
      checkSessionStatus();
      
      // 세션 상태 확인 타이머 시작
      startSessionCheckTimer();
      
      // 저장된 작업 상태 복원
      restoreWorkState();
      
      // 페이지 언로드 시 작업 상태 저장
      $(window).on('beforeunload', function() {
        saveCurrentWorkState();
      });
      
      // 사용자 활동 감지 시 세션 갱신
      let userActivityTimer = null;
      const resetUserActivityTimer = function() {
        if (userActivityTimer) {
          clearTimeout(userActivityTimer);
        }
        userActivityTimer = setTimeout(function() {
          refreshSession();
        }, 10 * 60 * 1000); // 10분 후 갱신
      };
      
      // 사용자 활동 이벤트 리스너
      $(document).on('mousemove keypress click scroll', resetUserActivityTimer);
      
      console.log('[session_manager.js] 세션 관리자 초기화 완료');
    }
  }
  
  // 전역 함수로 노출
  window.sessionManager = {
    refreshSession: refreshSession,
    checkSessionStatus: checkSessionStatus,
    startSessionRefreshTimer: startSessionRefreshTimer,
    stopSessionTimers: stopSessionTimers,
    handleSessionExpired: handleSessionExpired
  };
  
  // 초기화 실행
  initializeSessionManager();
}); 