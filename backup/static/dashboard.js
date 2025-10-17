// dashboard.js
$(function() {
  console.log('[dashboard.js] dashboard.js loaded');
  
  // 숫자 포맷팅 함수
  function format2f(val) {
    if (isNaN(val) || !isFinite(val)) return "0.00";
    return Number(val).toFixed(2);
  }
  
  // 역할명 매핑(한글명)
  window.dashboardRoleMap = {
    web: '웹서버',
    was: 'WAS',
    java: 'JAVA',
    search: '검색',
    ftp: 'FTP',
    db: 'DB'
  };
  
  function updateDashboardStats(stats) {
    console.log('[dashboard.js] updateDashboardStats', stats);
    
    // 기본 서버 통계
    $('#total-servers').text(stats.total_servers);
    $('#running-servers').text(stats.running_servers);
    $('#stopped-servers').text(stats.stopped_servers);
    
    // CPU 리소스 정보
    $('#node-total-cpu').text(stats.node_total_cpu + ' 코어');
    $('#vm-total-cpu').text(stats.vm_total_cpu + ' 코어');
    $('#vm-used-cpu').text(stats.vm_used_cpu + ' 코어');
    
    // 메모리 리소스 정보
    $('#node-total-memory').text(stats.node_total_memory_gb + ' GB');
    $('#vm-total-memory').text(stats.vm_total_memory_gb + ' GB');
    $('#vm-used-memory').text(stats.vm_used_memory_gb + ' GB');
    
    // 원형 그래프 업데이트
    updateResourceRing('cpu', stats.cpu_usage_percent);
    updateResourceRing('memory', stats.memory_usage_percent);
  }
  
  function updateResourceRing(type, percentage) {
    const circumference = 2 * Math.PI * 50; // r=50
    const offset = circumference - (percentage / 100) * circumference;
    
    $(`#${type}-progress`).css('stroke-dashoffset', offset);
    $(`#${type}-usage-percent`).text(percentage + '%');
    
    // 색상 변경 (사용률에 따라)
    let color = '#28a745'; // 기본 녹색
    if (percentage > 80) {
      color = '#dc3545'; // 빨간색 (80% 이상)
    } else if (percentage > 60) {
      color = '#ffc107'; // 노란색 (60% 이상)
    }
    
    $(`#${type}-progress`).css('stroke', color);
  }
  
  // 대시보드 서버 요약 패널 렌더링
  function loadDashboardServers() {
    console.log('[dashboard.js] loadDashboardServers 호출');
    $('#server-summary-container').html('<div class="text-center text-muted py-4">서버 정보를 불러오는 중...</div>');
    
    $.get('/all_server_status', function(res) {
      console.log('[dashboard.js] /all_server_status 응답:', res);
      const servers = res.servers || {};
      let html = '';
      
      const statusBadge = s => {
        switch(s.status) {
          case 'running': return '<span class="badge bg-success">실행 중</span>';
          case 'stopped': return '<span class="badge bg-secondary">중지됨</span>';
          case 'paused': return '<span class="badge bg-warning">일시정지</span>';
          case 'suspended': return '<span class="badge bg-info">일시중단</span>';
          default: return `<span class="badge bg-dark">${s.status}</span>`;
        }
      };
      
      const roleName = s => window.dashboardRoleMap && window.dashboardRoleMap[s.role] ? window.dashboardRoleMap[s.role] : (s.role || '-');
      const ipList = s => (s.network_devices && s.network_devices.length > 0) ? s.network_devices.map(nd=>nd.ip_address).join(', ') : '-';
      const serverArr = Object.entries(servers);
      
      if (serverArr.length === 0) {
        html = '<div class="text-center text-muted py-4">등록된 서버가 없습니다.</div>';
      } else {
        serverArr.forEach(([name, s]) => {
          html += `<div class="server-list-item">
            <div class="server-icon">
              <i class="fas fa-server"></i>
            </div>
            <div class="server-info">
              <div class="server-name">${s.name}</div>
              <div class="server-role">
                <span class="badge bg-primary">${roleName(s)}</span>
              </div>
              <div class="server-resources">
                <span class="resource-badge">
                  <i class="fas fa-microchip"></i>
                  ${parseInt(s.cpu || 0)}코어
                </span>
                <span class="resource-badge">
                  <i class="fas fa-memory"></i>
                  ${format2f((s.memory || 0) / 1024 / 1024 / 1024)}GB
                </span>
              </div>
              <div class="server-ip">
                <i class="fas fa-network-wired me-1"></i>
                ${ipList(s)}
              </div>
              <div class="server-status">
                ${statusBadge(s)}
              </div>
            </div>
          </div>`;
        });
      }
      
      $('#server-summary-container').html(html);
      
      // 통계 업데이트
      if (res.stats) {
        updateDashboardStats(res.stats);
      }
    }).fail(function(xhr) {
      console.error('[dashboard.js] /all_server_status 실패:', xhr);
      $('#server-summary-container').html('<div class="text-center text-danger py-4">서버 정보를 불러오지 못했습니다.</div>');
    });
  }
  
  // 대시보드 스토리지 요약 패널 렌더링
  function loadDashboardStorage() {
    console.log('[dashboard.js] loadDashboardStorage 호출');
    $('#dashboard-storage-panel').html('<div class="text-center text-muted py-4">스토리지 정보를 불러오는 중...</div>');
    
    $.get('/proxmox_storage', function(res) {
      const storages = res.storages || [];
      let html = '';
      
      if (storages.length === 0) {
        html = '<div class="text-center text-muted py-4">등록된 스토리지가 없습니다.</div>';
      } else {
        html = '<div class="table-responsive"><table class="table table-sm table-bordered mb-0"><thead><tr>' +
          '<th>스토리지명</th><th>타입</th><th>총 용량(GB)</th><th>사용 가능(GB)</th><th>사용률</th></tr></thead><tbody>';
        storages.forEach(function(s) {
          const usedPercent = s.total > 0 ? Math.round((s.used / s.total) * 100) : 0;
          const storageType = (s.type === 'lvmthin' || s.type === 'lvm' || s.storage === 'local' || s.storage === 'local-lvm') ? 'HDD' : (s.type === 'dir' ? 'SSD' : s.type);
          html += `<tr>
            <td>${s.storage}</td>
            <td>${storageType}</td>
            <td>${format2f(s.total / 1024 / 1024 / 1024)}</td>
            <td>${format2f((s.total - s.used) / 1024 / 1024 / 1024)}</td>
            <td>
              <div class='progress' style='height: 16px;'>
                <div class='progress-bar' role='progressbar' style='width: ${usedPercent}%;'>${usedPercent}%</div>
              </div>
            </td>
          </tr>`;
        });
        html += '</tbody></table></div>';
      }
      
      $('#dashboard-storage-panel').html(html);
    }).fail(function(xhr) {
      console.error('[dashboard.js] 스토리지 정보 로드 실패:', xhr);
      $('#dashboard-storage-panel').html('<div class="text-center text-danger py-4">스토리지 정보를 불러오지 못했습니다.</div>');
    });
  }
  
  // 최초 진입/새로고침/탭 전환 시 항상 최신 상태로 갱신
  loadDashboardServers();
  loadDashboardStorage();
  
  // 서버 요약 확장/축소 토글 기능
  let serverSummaryExpanded = false;
  
  $('#toggle-server-summary-btn').on('click', function() {
    console.log('[dashboard.js] 토글 버튼 클릭됨');
    const container = $('#server-summary-container');
    const icon = $('#toggle-server-summary-icon');
    
    if (serverSummaryExpanded) {
      // 축소
      container.removeClass('expanded maximized');
      icon.removeClass('fa-compress-alt').addClass('fa-expand-alt');
      serverSummaryExpanded = false;
      console.log('[dashboard.js] 서버 요약 축소됨');
    } else {
      // 확장
      container.addClass('expanded');
      icon.removeClass('fa-expand-alt').addClass('fa-compress-alt');
      serverSummaryExpanded = true;
      console.log('[dashboard.js] 서버 요약 확장됨');
    }
  });
  
  // 서버 요약 컨테이너 더블클릭으로 최대화/복원 (이벤트 위임 사용)
  $(document).on('dblclick', '#server-summary-container', function(e) {
    console.log('[dashboard.js] 서버 요약 컨테이너 더블클릭됨');
    e.preventDefault();
    e.stopPropagation();
    
    const container = $(this);
    const icon = $('#toggle-server-summary-icon');
    
    if (container.hasClass('maximized')) {
      // 복원
      container.removeClass('maximized');
      icon.removeClass('fa-compress-alt').addClass('fa-expand-alt');
      serverSummaryExpanded = false;
      console.log('[dashboard.js] 서버 요약 최대화에서 복원됨');
    } else {
      // 최대화
      container.addClass('maximized');
      icon.removeClass('fa-expand-alt').addClass('fa-compress-alt');
      serverSummaryExpanded = true;
      console.log('[dashboard.js] 서버 요약 최대화됨');
    }
  });
  
  // 새로고침 버튼 이벤트
  $('#dashboard-refresh-btn').on('click', function() {
    console.log('[dashboard.js] #dashboard-refresh-btn 클릭');
    loadDashboardServers();
  });
  
  $('#dashboard-storage-refresh-btn').on('click', function() {
    console.log('[dashboard.js] #dashboard-storage-refresh-btn 클릭');
    loadDashboardStorage();
  });
}); 
