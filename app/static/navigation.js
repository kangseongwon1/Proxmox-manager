/**
 * 상단 네비게이션 공통 관리
 * SSE 알림 시스템 중앙 집중 관리
 */

console.log('[navigation.js] 상단 네비게이션 관리 모듈 로드됨');

// 전역 알림 관리
window.systemNotifications = window.systemNotifications || [];
window.notificationEventSource = window.notificationEventSource || null;

/**
 * SSE 연결 초기화
 */
function initNotificationStream() {
  if (window.notificationEventSource) {
    window.notificationEventSource.close();
  }
  
  window.notificationEventSource = new EventSource('/notifications/stream');
  
  window.notificationEventSource.onmessage = function(event) {
    console.log(`🔔 SSE 이벤트 수신:`, event.data);
    try {
      const data = JSON.parse(event.data);
      console.log(`🔔 SSE 파싱된 데이터:`, data);
      
      if (data.type === 'notification' || data.type === 'backup' || 
          data.type === 'server_start' || data.type === 'server_stop' || 
          data.type === 'server_reboot' || data.type === 'server_deletion' ||
          data.type === 'server_creation' || data.type === 'error' ||
          data.type === 'ansible_role') {
        console.log(`🔔 SSE로 실시간 알림 수신: ${data.title}`);
        
        // 중복 체크 (id 우선, 없으면 title+message)
        let isDuplicate = false;
        try {
          if (Array.isArray(window.systemNotifications) && window.systemNotifications.length > 0) {
            if (typeof data.id !== 'undefined') {
              isDuplicate = window.systemNotifications.some(function(existing) {
                return existing.id === data.id;
              });
            } else {
              isDuplicate = window.systemNotifications.some(function(existing) {
                return existing.title === data.title && existing.message === data.message;
              });
            }
          }
        } catch (dupErr) {
          console.warn('[navigation.js] 중복 체크 오류:', dupErr);
        }
        
        if (!isDuplicate) {
          window.addSystemNotification(
            data.severity || 'info',
            data.title,
            data.message,
            data.details,
            data.id
          );
          console.log('[navigation.js] 알림 추가 및 드롭다운 갱신 완료');
        } else {
          // 중복이라도 배지/리스트가 비정상 상태일 수 있으므로 강제 갱신
          try {
            console.log('[navigation.js] 중복 알림 감지 → 드롭다운 강제 갱신');
            updateNotificationDropdown();
          } catch (updErr) {
            console.warn('[navigation.js] 드롭다운 강제 갱신 오류:', updErr);
          }
        }
        
        // 백업 관련 이벤트 처리
        if (data.type === 'backup') {
          handleBackupNotification(data);
        }
        
        // 서버 작업 UI 업데이트는 중복 여부와 무관하게 항상 수행
        if (data.type === 'server_start' || data.type === 'server_stop' ||
            data.type === 'server_reboot' || data.type === 'server_deletion' ||
            data.type === 'node_exporter_install' || data.type === 'ansible_role' ||
            data.title.includes('시작') || data.title.includes('중지') ||
            data.title.includes('재시작') || data.title.includes('삭제') ||
            data.title.includes('완료') || data.title.includes('성공') ||
            data.title.includes('실패') || data.title.includes('역할 할당')) {
          try {
            updateServerUIAfterAction(data);
          } catch (uiErr) {
            console.warn('[navigation.js] 서버 작업 UI 업데이트 중 오류:', uiErr);
          }
        }
      } else {
        console.log(`🔔 SSE 다른 타입 이벤트:`, data.type);
      }
    } catch (error) {
      console.error('SSE 알림 파싱 오류:', error);
    }
  };
  
  window.notificationEventSource.onerror = function(event) {
    console.error('SSE 연결 오류:', event);
    
    // 기존 연결 정리
    if (window.notificationEventSource) {
      window.notificationEventSource.close();
      window.notificationEventSource = null;
    }
    
    // 3초 후 재연결 시도
    setTimeout(function() {
      console.log('🔄 SSE 재연결 시도...');
      initNotificationStream();
    }, 3000);
  };
  
  console.log('🔗 SSE 알림 스트림 연결됨');
}

/**
 * SSE 연결 상태 확인
 */
function checkSSEConnection() {
  if (window.notificationEventSource) {
    console.log('🔗 SSE 연결 상태:', window.notificationEventSource.readyState);
    console.log('🔗 SSE URL:', window.notificationEventSource.url);
    
    if (window.notificationEventSource.readyState === EventSource.CONNECTING) {
      console.log('🔄 SSE 연결 중...');
    } else if (window.notificationEventSource.readyState === EventSource.OPEN) {
      console.log('✅ SSE 연결됨');
    } else if (window.notificationEventSource.readyState === EventSource.CLOSED) {
      console.log('❌ SSE 연결 끊어짐');
    }
  } else {
    console.log('❌ SSE 연결 없음');
  }
}

/**
 * SSE 연결 재시작
 */
function restartSSE() {
  console.log('🔄 SSE 연결 강제 재시작...');
  if (window.notificationEventSource) {
    window.notificationEventSource.close();
    window.notificationEventSource = null;
  }
  setTimeout(() => {
    initNotificationStream();
  }, 1000);
}

/**
 * 알림 추가 함수 (상단 네비게이션 드롭다운 업데이트)
 */
function addSystemNotification(severity, title, message, details, id) {
  console.log(`🔔 알림 추가: ${title} (${severity})`);
  
  // 알림 객체 생성
  const notification = {
    id: id || Date.now(),
    type: severity,
    title: title,
    message: message,
    details: details,
    time: new Date().toLocaleTimeString('ko-KR', {hour12:false})
  };
  
  // 전역 알림 배열에 추가 (최대 10개 유지)
  window.systemNotifications.unshift(notification);
  if (window.systemNotifications.length > 10) {
    window.systemNotifications.length = 10;
  }
  
  // 상단 네비게이션 드롭다운 업데이트
  updateNotificationDropdown();
  
  console.log(`🔔 현재 알림 수: ${window.systemNotifications.length}`);
}

/**
 * 상단 네비게이션 드롭다운 업데이트
 */
function updateNotificationDropdown() {
  const $list = $('#notification-list');
  const $badge = $('#notification-badge');
  
  if (!window.systemNotifications || window.systemNotifications.length === 0) {
    $list.html('<li class="text-center text-muted py-3">알림이 없습니다</li>');
    $badge.hide();
    return;
  }
  
  // 알림 배지 업데이트
  $badge.text(window.systemNotifications.length).show();
  
  // 알림 목록 HTML 생성
  let html = '';
  window.systemNotifications.forEach(function(noti, idx) {
    const severityClass = noti.type === 'error' ? 'text-danger' : 
                         noti.type === 'success' ? 'text-success' : 'text-info';
    const severityIcon = noti.type === 'error' ? 'fas fa-exclamation-circle' : 
                        noti.type === 'success' ? 'fas fa-check-circle' : 'fas fa-info-circle';
    
    html += `
      <li class="dropdown-item-text px-3 py-2 border-bottom">
        <div class="d-flex align-items-start">
          <i class="${severityIcon} ${severityClass} me-2 mt-1"></i>
          <div class="flex-grow-1">
            <div class="fw-bold text-truncate" style="max-width: 300px;" title="${noti.title}">${noti.title}</div>
            <div class="text-muted small text-truncate" style="max-width: 300px;" title="${noti.message}">${noti.message}</div>
            <div class="text-muted small">${noti.time}</div>
          </div>
        </div>
      </li>
    `;
  });
  
  $list.html(html);
}

/**
 * 초기 알림 로드
 */
function loadInitialNotifications() {
  console.log('[navigation.js] 초기 알림 로드 시작');
  $.get('/notifications', { _ts: Date.now() })
    .done(function(response) {
      console.log('[navigation.js] 초기 알림 로드 성공:', response);
      if (response.notifications && response.notifications.length > 0) {
        // 기존 알림 초기화
        window.systemNotifications = [];
        
        // 서버에서 받은 알림들을 추가
        response.notifications.forEach(function(noti) {
          window.addSystemNotification(
            noti.severity || 'info',
            noti.title,
            noti.message,
            noti.details,
            noti.id
          );
        });
      }
    })
    .fail(function(xhr, status, error) {
      console.error('[navigation.js] 초기 알림 로드 실패:', error);
    });
}

/**
 * 확인 모달 함수
 */
function confirmModal(message) {
  return new Promise((resolve) => {
    const modal = $(`
      <div class="modal fade" id="confirmModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">확인</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              ${message}
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="button" class="btn btn-primary" id="confirmOk">확인</button>
            </div>
          </div>
        </div>
      </div>
    `);
    
    $('body').append(modal);
    const bsModal = new bootstrap.Modal(modal[0]);
    bsModal.show();
    
    modal.find('#confirmOk').on('click', function() {
      bsModal.hide();
      modal.remove();
      resolve(true);
    });
    
    modal.on('hidden.bs.modal', function() {
      modal.remove();
      resolve(false);
    });
  });
}

/**
 * 모든 알림 삭제 버튼 핸들러
 */
function setupNotificationHandlers() {
  // 모든 알림 삭제 버튼 핸들러
  $(document).off('click', '#clear-all-notifications').on('click', '#clear-all-notifications', async function(e) {
    e.preventDefault();
    const ok = await confirmModal('모든 알림을 삭제하시겠습니까?');
    if (!ok) return;
    
    // 즉시 클라이언트 알림 드롭다운 갱신
    window.systemNotifications = [];
    updateNotificationDropdown();
    
    // 서버에 삭제 요청
    $.post('/notifications/clear-all', function(res) {
      console.log('[navigation.js] 모든 알림 삭제 성공');
    }).fail(function(xhr) {
      console.error('[navigation.js] 알림 삭제 실패:', xhr);
      window.addSystemNotification('error', '알림 삭제 실패', xhr.responseJSON?.error || xhr.statusText);
    });
  });
}

/**
 * 서버 작업 완료 후 UI 업데이트
 */
function updateServerUIAfterAction(notificationData) {
  try {
    const message = notificationData.message || '';
    const title = notificationData.title || '';
    const details = notificationData.details || '';
    
    // 서버명 추출 우선순위: details의 '서버명:' → message 패턴 → title 패턴
    let serverName = null;
    
    // 1) details에서 추출 (예: '서버명: test')
    if (!serverName && typeof details === 'string' && details.indexOf('서버명:') !== -1) {
      const m = details.match(/서버명:\s*([^\s\n]+)/);
      if (m && m[1]) serverName = m[1].trim();
    }
    
    // 2) message에서 추출 (예: '서버 test이 성공적으로 중지되었습니다.')
    if (!serverName && typeof message === 'string' && message.indexOf('서버 ') !== -1) {
      const m2 = message.match(/서버\s+([^\s이가은는을를,\.]+)/);
      if (m2 && m2[1]) serverName = m2[1].trim();
    }
    
    // 3) title에서 추출 (예: '서버 test 삭제 완료')
    if (!serverName && typeof title === 'string' && title.indexOf('서버 ') !== -1) {
      const m3 = title.match(/서버\s+(\w+)/);
      if (m3 && m3[1]) serverName = m3[1].trim();
    }
    
    // 4) 일괄 작업인 경우 서버명을 null로 설정 (전체 새로고침)
    if (!serverName && (title.includes('일괄') || title.includes('대량'))) {
      serverName = null; // 일괄 작업은 서버명 없이 처리
      console.log(`[navigation.js] 일괄 작업 감지: ${title}`);
    }
    
    if (serverName) {
      console.log(`[navigation.js] 서버 작업 완료 UI 업데이트: ${serverName} - ${title}`);
      
      // 삭제 완료인 경우 서버 행을 완전히 제거
      if (title.includes('삭제') && title.includes('완료')) {
        const $serverRow = $(`tr[data-server="${serverName}"]`);
        if ($serverRow.length > 0) {
          console.log(`[navigation.js] 서버 행 제거: ${serverName}`);
          $serverRow.fadeOut(500, function() {
            $(this).remove();
            // 서버 개수 업데이트
            const remainingServers = $('tr[data-server]').length;
            console.log(`[navigation.js] 남은 서버 수: ${remainingServers}`);
          });
        }
        
        // 삭제 완료 시 서버 목록 강제 새로고침
        console.log(`[navigation.js] 삭제 완료 - 서버 목록 강제 새로고침: ${serverName}`);
        setTimeout(function() {
          if (typeof loadActiveServers === 'function') {
            loadActiveServers();
          }
        }, 1000);
      } else {
        // 일반적인 작업 완료/실패 시 서버 목록 새로고침 (실시간 조회)
        if (typeof loadActiveServers === 'function') {
          console.log('[navigation.js] 서버 목록 새로고침 (작업 완료/실패)');
          loadActiveServers();
        }
        
        // 역할 할당 완료 시 서버 시작과 동일한 처리
        if ((title.includes('역할 할당') && title.includes('완료')) || 
            (title.includes('일괄 역할 할당') && title.includes('완료'))) {
          console.log(`[navigation.js] 역할 할당 완료 - 서버 목록 새로고침: ${serverName || '일괄'}`);
          
          // 서버 시작과 동일한 방식으로 처리
          if (typeof loadActiveServers === 'function') {
            console.log(`[navigation.js] 역할 할당 완료 - loadActiveServers() 호출`);
            loadActiveServers();
          }
        }
        
        // 작업 실패 시 버튼 상태 복원
        if (title.includes('실패')) {
          const $serverRow = $(`tr[data-server="${serverName}"]`);
          if ($serverRow.length > 0) {
            // 모든 액션 버튼 활성화 및 원래 텍스트로 복원
            $serverRow.find('.start-btn, .stop-btn, .reboot-btn, .delete-btn').each(function() {
              const $btn = $(this);
              const action = $btn.hasClass('start-btn') ? 'start' : 
                            $btn.hasClass('stop-btn') ? 'stop' : 
                            $btn.hasClass('reboot-btn') ? 'reboot' : 'delete';
              
              // 버튼 활성화 및 원래 텍스트로 복원
              $btn.prop('disabled', false);
              
              if (action === 'start') {
                $btn.html('<i class="fas fa-play me-1"></i>시작');
              } else if (action === 'stop') {
                $btn.html('<i class="fas fa-stop me-1"></i>중지');
              } else if (action === 'reboot') {
                $btn.html('<i class="fas fa-redo me-1"></i>재시작');
              } else if (action === 'delete') {
                $btn.html('<i class="fas fa-trash me-1"></i>삭제');
              }
            });
          }
        }
      }
      
      // 백업 목록 새로고침 (백업 관련 작업인 경우)
      if (message.includes('백업') && typeof loadBackupData === 'function') {
        console.log('[navigation.js] 백업 목록 새로고침 (작업 완료)');
        loadBackupData();
      }
    } else {
      // 일괄 작업인 경우 전체 새로고침
      if (title.includes('일괄') || title.includes('대량')) {
        console.log(`[navigation.js] 일괄 작업 - 전체 새로고침: ${title}`);
        if (typeof loadActiveServers === 'function') {
          loadActiveServers();
        }
      } else {
        console.warn('[navigation.js] 서버명을 추출할 수 없음:', { title, message, details });
      }
    }
    
  } catch (error) {
    console.error('[navigation.js] 서버 작업 완료 UI 업데이트 실패:', error);
  }
}

/**
 * 백업 알림 처리
 */
function handleBackupNotification(data) {
  console.log('[navigation.js] 백업 알림 처리:', data);
  
  // 서버 이름 추출 (제목에서)
  const serverNameMatch = data.title.match(/서버\s+(\w+)/);
  const serverName = serverNameMatch ? serverNameMatch[1] : null;
  
  if (data.title.includes('백업 완료') || data.title.includes('백업 성공')) {
    console.log('[navigation.js] 백업 완료:', serverName);
    
    // 백업 중인 서버 목록에서 제거
    if (serverName && window.backingUpServers) {
      const index = window.backingUpServers.indexOf(serverName);
      if (index > -1) {
        window.backingUpServers.splice(index, 1);
      }
    }
    
    // 서버 작업 버튼 활성화
    if (serverName && typeof updateBackupActionButtons === 'function') {
      updateBackupActionButtons(serverName, false);
    }
    
    // 서버 목록 새로고침
    if (typeof loadActiveServers === 'function') {
      console.log('[navigation.js] 서버 목록 새로고침 (백업 완료)');
      loadActiveServers();
    }
    
    // 백업 목록 새로고침
    if (typeof loadBackupData === 'function') {
      console.log('[navigation.js] 백업 목록 새로고침 (백업 완료)');
      loadBackupData();
    }
    
  } else if (data.title.includes('백업 실패') || data.title.includes('백업 오류') || data.title.includes('백업 타임아웃')) {
    console.log('[navigation.js] 백업 실패/타임아웃:', serverName);
    
    // 백업 중인 서버 목록에서 제거
    if (serverName && window.backingUpServers) {
      const index = window.backingUpServers.indexOf(serverName);
      if (index > -1) {
        window.backingUpServers.splice(index, 1);
      }
    }
    
    // 서버 작업 버튼 활성화
    if (serverName && typeof updateBackupActionButtons === 'function') {
      updateBackupActionButtons(serverName, false);
    }
    
    // 서버 목록 새로고침
    if (typeof loadActiveServers === 'function') {
      console.log('[navigation.js] 서버 목록 새로고침 (백업 실패)');
      loadActiveServers();
    }
    
  } else if (data.title.includes('백업 복원 완료')) {
    console.log('[navigation.js] 백업 복원 완료:', data.details);
    
    // 서버 목록 새로고침
    if (typeof loadActiveServers === 'function') {
      console.log('[navigation.js] 서버 목록 새로고침 (복원 완료)');
      loadActiveServers();
    }
    
    // 백업 목록 새로고침
    if (typeof loadBackupData === 'function') {
      console.log('[navigation.js] 백업 목록 새로고침 (복원 완료)');
      loadBackupData();
    }
  }
}

/**
 * 네비게이션 초기화
 */
function initNavigation() {
  console.log('[navigation.js] 네비게이션 초기화 시작');
  
  // SSE 연결 초기화
  initNotificationStream();
  
  // 초기 알림 로드 제거 - SSE로 실시간 알림 처리
  // loadInitialNotifications();
  
  // 이벤트 핸들러 설정
  setupNotificationHandlers();
  
  console.log('[navigation.js] 네비게이션 초기화 완료');
}

// 전역 함수로 노출
window.initNotificationStream = initNotificationStream;
window.checkSSEConnection = checkSSEConnection;
window.restartSSE = restartSSE;
window.addSystemNotification = addSystemNotification;
window.updateNotificationDropdown = updateNotificationDropdown;
window.loadInitialNotifications = loadInitialNotifications;
window.confirmModal = confirmModal;
window.updateServerUIAfterAction = updateServerUIAfterAction;
window.handleBackupNotification = handleBackupNotification;
window.initNavigation = initNavigation;

// 페이지 로드 시 자동 초기화
$(document).ready(function() {
  initNavigation();
});
