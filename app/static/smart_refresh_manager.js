/**
 * 스마트 실시간 갱신 관리자
 * 사용자 작업 중에는 갱신을 중단하고, 작업 완료 시 자동으로 재개하는 시스템
 */

$(function() {

  // 스마트 갱신 관리자 상태
  const smartRefreshManager = {
    refreshInterval: null,
    refreshRate: 10000, // 10초
    isUserWorking: false,
    isRefreshPaused: false,
    lastUserActivity: Date.now(),
    userActivityTimeout: 30000, // 30초 동안 활동 없으면 자동 갱신 재개
    pendingRefresh: false,
    
    // 사용자 작업을 감지하는 요소들
    workIndicators: {
      activeModals: 0,
      activeForms: 0,
      focusedInputs: new Set(),
      openDropdowns: 0,
      dragOperations: 0,
      inlineEditing: 0
    }
  };

  /**
   * 사용자가 작업 중인지 확인
   */
  function isUserCurrentlyWorking() {
    const indicators = smartRefreshManager.workIndicators;
    
    // 1. 모달이 열려있는 경우
    if (indicators.activeModals > 0) {
      return true;
    }
    
    // 2. 입력 폼에 포커스가 있는 경우
    if (indicators.focusedInputs.size > 0) {
      return true;
    }
    
    // 3. 드롭다운이 열려있는 경우
    if (indicators.openDropdowns > 0) {
      return true;
    }
    
    // 4. 드래그 작업 중인 경우
    if (indicators.dragOperations > 0) {
      return true;
    }
    
    // 5. 인라인 편집 중인 경우
    if (indicators.inlineEditing > 0) {
      return true;
    }
    
    // 6. 일괄 작업이 진행 중인 경우
    if (window.isBulkOperationInProgress === true) {
      return true;
    }
    
    // 7. 최근 사용자 활동이 있었는지 확인 (타이핑, 클릭 등)
    const timeSinceLastActivity = Date.now() - smartRefreshManager.lastUserActivity;
    if (timeSinceLastActivity < 5000) { // 5초 이내 활동
      return true;
    }
    
    return false;
  }

  /**
   * 갱신 상태 업데이트
   */
  function updateRefreshStatus() {
    const wasWorking = smartRefreshManager.isUserWorking;
    const isWorking = isUserCurrentlyWorking();
    
    smartRefreshManager.isUserWorking = isWorking;
    
    // 작업 상태가 변경된 경우
    if (wasWorking !== isWorking) {
      if (isWorking) {
        pauseAutoRefresh();
      } else {
        resumeAutoRefresh();
      }
    }
  }

  /**
   * 자동 갱신 일시정지
   */
  function pauseAutoRefresh() {
    if (!smartRefreshManager.isRefreshPaused) {
      smartRefreshManager.isRefreshPaused = true;
      showRefreshStatus('paused');
    }
  }

  /**
   * 자동 갱신 재개
   */
  function resumeAutoRefresh() {
    if (smartRefreshManager.isRefreshPaused) {
      smartRefreshManager.isRefreshPaused = false;
      showRefreshStatus('active');
      
      // 미뤄진 갱신이 있다면 즉시 실행
      if (smartRefreshManager.pendingRefresh) {
        executeRefresh();
        smartRefreshManager.pendingRefresh = false;
      }
    }
  }

  /**
   * 실제 갱신 실행
   */
  function executeRefresh() {
    // 대시보드에서만 리소스 상태 갱신 (인스턴스 페이지 제외)
    const currentHash = window.location.hash;
    
    if (currentHash === '#dashboard' || currentHash === '') {
      if (typeof window.loadActiveServers === 'function') {
        // 상태 변경 확인 후 새로고침
        checkServerStatusChanges();
      }
    }
    
    // 인스턴스 페이지에서는 자동 새로고침 하지 않음
    // 사용자가 작업을 수행할 때만 상태 업데이트
    
    // 알림은 페이지 로드 시에만 로드하고, 이후에는 자동 갱신하지 않음
    // (알림이 새로 생성될 때만 표시)
  }

  /**
   * 서버 상태 및 설정 변경 확인
   */
  function checkServerStatusChanges() {
    // 현재 서버 상태 및 설정 저장
    const currentServerStates = {};
    $('.server-row').each(function() {
      const serverName = $(this).data('server');
      const currentStatus = $(this).data('status');
      const currentRole = $(this).data('role');
      currentServerStates[serverName] = {
        status: currentStatus,
        role: currentRole
      };
    });

    // 서버 상태만 조회 (전체 새로고침 대신)
    $.get('/api/all_server_status', function(res) {
      let hasChange = false;
      
      // 상태 및 설정 변경 확인
      for (const [serverName, serverData] of Object.entries(res.servers || {})) {
        const previousState = currentServerStates[serverName];
        if (!previousState) continue;
        
        const currentStatus = serverData.status;
        const currentRole = serverData.role;
        
        // 상태 변경 확인
        if (previousState.status !== currentStatus) {
          console.log(`[smart_refresh] 서버 상태 변경 감지: ${serverName} (${previousState.status} → ${currentStatus})`);
          hasChange = true;
          break;
        }
        
        // 역할 변경 확인
        if (previousState.role !== currentRole) {
          console.log(`[smart_refresh] 서버 역할 변경 감지: ${serverName} (${previousState.role} → ${currentRole})`);
          hasChange = true;
          break;
        }
      }
      
      // 변경이 있을 때만 전체 새로고침
      if (hasChange) {
        console.log('[smart_refresh] 변경 감지로 인한 새로고침 실행');
        window.loadActiveServers();
      } else {
        console.log('[smart_refresh] 변경 없음 - 새로고침 건너뜀');
      }
    }).fail(function(xhr) {
      console.error('[smart_refresh] 서버 상태 조회 실패:', xhr);
      // 에러 시에는 전체 새로고침
      window.loadActiveServers();
    });
  }

  /**
   * 갱신 상태 UI 표시 (자동 갱신 창 제거)
   */
  function showRefreshStatus(status) {
    // 자동 갱신 창 제거 - 더 이상 UI 표시하지 않음
    // console.log(`[smart_refresh] 갱신 상태: ${status}`);
  }

  /**
   * 임시 메시지 표시
   */
  function showTemporaryMessage(message) {
    const $indicator = $('#refresh-status-indicator');
    const originalText = $indicator.find('.status-text').text();
    
    $indicator.find('.status-text').text(message);
    
    setTimeout(() => {
      $indicator.find('.status-text').text(originalText);
    }, 2000);
  }

  /**
   * 스마트 갱신 타이머 시작
   */
  function startSmartRefreshTimer() {
    if (smartRefreshManager.refreshInterval) {
      clearInterval(smartRefreshManager.refreshInterval);
    }
    
    smartRefreshManager.refreshInterval = setInterval(function() {
      updateRefreshStatus();
      
      if (!smartRefreshManager.isRefreshPaused) {
        executeRefresh();
      } else {
        // 갱신이 일시정지된 상태라면 미뤄진 갱신으로 표시
        smartRefreshManager.pendingRefresh = true;
      }
    }, smartRefreshManager.refreshRate);
  }

  /**
   * 이벤트 리스너 설정
   */
  function setupEventListeners() {
    // 1. 모달 관련 이벤트
    $(document).on('show.bs.modal', '.modal', function() {
      smartRefreshManager.workIndicators.activeModals++;
    });
    
    $(document).on('hide.bs.modal', '.modal', function() {
      smartRefreshManager.workIndicators.activeModals = Math.max(0, smartRefreshManager.workIndicators.activeModals - 1);
    });
    
    // 2. 입력 폼 포커스 관련 이벤트
    $(document).on('focus', 'input, textarea, select', function() {
      const elementId = $(this).attr('id') || $(this).attr('name') || 'unnamed';
      smartRefreshManager.workIndicators.focusedInputs.add(elementId);
      smartRefreshManager.lastUserActivity = Date.now();
    });
    
    $(document).on('blur', 'input, textarea, select', function() {
      const elementId = $(this).attr('id') || $(this).attr('name') || 'unnamed';
      smartRefreshManager.workIndicators.focusedInputs.delete(elementId);
    });
    
    // 3. 드롭다운 관련 이벤트
    $(document).on('show.bs.dropdown', function() {
      smartRefreshManager.workIndicators.openDropdowns++;
    });
    
    $(document).on('hide.bs.dropdown', function() {
      smartRefreshManager.workIndicators.openDropdowns = Math.max(0, smartRefreshManager.workIndicators.openDropdowns - 1);
    });
    
    // 4. 사용자 활동 감지 (키보드, 마우스)
    $(document).on('keydown input change click', function(e) {
      smartRefreshManager.lastUserActivity = Date.now();
    });
    
    // 5. 체크박스 선택 감지 (추가)
    $(document).on('change', '.server-checkbox, #select-all-servers', function() {
      smartRefreshManager.lastUserActivity = Date.now();
    });
    
    // 5. 드래그 앤 드롭 관련 이벤트
    $(document).on('dragstart', function() {
      smartRefreshManager.workIndicators.dragOperations++;
    });
    
    $(document).on('dragend drop', function() {
      smartRefreshManager.workIndicators.dragOperations = Math.max(0, smartRefreshManager.workIndicators.dragOperations - 1);
    });
    
    // 6. 체크박스 선택 상태 감지 (대량 작업 시)
    $(document).on('change', 'input[type="checkbox"]', function() {
      smartRefreshManager.lastUserActivity = Date.now();
    });
  }

  /**
   * 기존 폴링 시스템 비활성화
   */
  function disableOldPollingSystem() {
    // instances.js의 기존 폴링 중지
    if (window.stopServerStatusPolling && typeof window.stopServerStatusPolling === 'function') {
      window.stopServerStatusPolling();
    }
  }

  /**
   * 스마트 갱신 관리자 초기화
   */
  function initializeSmartRefreshManager() {
    // 기존 폴링 시스템 비활성화
    disableOldPollingSystem();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // 초기 상태 표시
    showRefreshStatus('active');
    
    // 스마트 갱신 타이머 시작
    startSmartRefreshTimer();
    
    // 전역 함수로 노출
    window.smartRefreshManager = {
      pause: pauseAutoRefresh,
      resume: resumeAutoRefresh,
      refresh: executeRefresh,
      isWorking: () => smartRefreshManager.isUserWorking,
      isPaused: () => smartRefreshManager.isRefreshPaused
    };
  }

  // 페이지 로드 완료 후 초기화 (다른 스크립트들이 로드된 후)
  setTimeout(initializeSmartRefreshManager, 1000);
});